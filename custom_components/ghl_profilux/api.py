"""Client für die GHL-Text-API (TCP, Port 10002).

Dieses Modul kennt Home Assistant nicht und lässt sich allein testen.
Der Port bedient nur einen Client gleichzeitig: pro Abfragerunde wird eine
Verbindung geöffnet und danach sofort wieder geschlossen.
"""
from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

DEFAULT_PORT = 10002
TIMEOUT = 5.0

MAX_SENSORS = 32
MAX_CHANNELS = 64
MAX_DOSERS = 32
MAX_LEVELS = 4
MAX_UNNAMED_RUN = 8


class GhlError(Exception):
    """Basisklasse für alle Fehler dieses Clients."""


class GhlConnectionError(GhlError):
    """Gerät nicht erreichbar oder Verbindung abgebrochen."""


class GhlNack(GhlError):
    """Das Gerät hat den Befehl mit NACK (code) abgelehnt."""

    def __init__(self, code: int, command: str) -> None:
        super().__init__(f"{command} -> NACK ({code})")
        self.code = code


class GhlAccessError(GhlNack):
    """NACK (-105): die API ist am Gerät ausgeschaltet oder nur lesend."""


class GhlOutdated(GhlError):
    """Firmware kennt die SYSTEM-Befehle nicht (älter als 7.52)."""


def _is_complete(text: str) -> bool:
    if text.startswith("NACK"):
        return ")" in text
    if text.startswith("ACK <"):
        return text.endswith(">")
    return False


class GhlConnection:
    """Eine offene Verbindung; Befehle laufen strikt nacheinander."""

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer

    async def _read_reply(self) -> str:
        buf = b""
        while True:
            chunk = await self._reader.read(512)
            if not chunk:
                raise GhlConnectionError("Das Gerät hat die Verbindung geschlossen")
            buf += chunk
            # Namen kommen im Windows-Zeichensatz (Umlaute), nicht in UTF-8.
            text = buf.decode("cp1252", errors="replace").strip()
            if _is_complete(text):
                return text

    async def query(self, command: str) -> str:
        """Sendet einen GET-Befehl und liefert den Wert zwischen < und >."""
        try:
            self._writer.write((command + "\n").encode("ascii"))
            await self._writer.drain()
            text = await asyncio.wait_for(self._read_reply(), TIMEOUT)
        except asyncio.TimeoutError as err:
            raise GhlConnectionError(f"Keine Antwort auf {command}") from err
        except OSError as err:
            raise GhlConnectionError(str(err)) from err

        if text.startswith("NACK"):
            code = int(text[text.index("(") + 1 : text.index(")")])
            if code == -105:
                raise GhlAccessError(code, command)
            raise GhlNack(code, command)

        value = text[5:-1]
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        return value

    async def get_float(self, command: str) -> float | None:
        """Zahl lesen; None, wenn das Gerät die Ressource nicht hat."""
        try:
            return float(await self.query(command))
        except GhlAccessError:
            raise
        except GhlNack:
            return None

    async def get_text(self, command: str) -> str | None:
        """Text lesen; None, wenn das Gerät die Ressource nicht hat."""
        try:
            return await self.query(command)
        except GhlAccessError:
            raise
        except GhlNack:
            return None


class GhlClient:
    """Öffnet Verbindungen zum Gerät, jeweils nur eine zur Zeit."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[GhlConnection]:
        async with self._lock:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), TIMEOUT
                )
            except (OSError, asyncio.TimeoutError) as err:
                raise GhlConnectionError(
                    f"Keine Verbindung zu {self.host}:{self.port}"
                ) from err
            try:
                yield GhlConnection(reader, writer)
            finally:
                writer.close()
                with contextlib.suppress(OSError, asyncio.TimeoutError):
                    await asyncio.wait_for(writer.wait_closed(), 2)


@dataclass
class ChannelInfo:
    name: str
    has_current: bool


@dataclass
class DoserInfo:
    name: str
    capacity: float


@dataclass
class Layout:
    """Was das Gerät hat. Wird einmal beim Start erkannt."""

    firmware: str
    serial: str
    sensors: dict[int, str] = field(default_factory=dict)
    channels: dict[int, ChannelInfo] = field(default_factory=dict)
    dosers: dict[int, DoserInfo] = field(default_factory=dict)
    levels: dict[int, str] = field(default_factory=dict)


async def read_identity(conn: GhlConnection) -> tuple[str, str]:
    """Firmware und Seriennummer; GhlOutdated, wenn SYSTEM fehlt."""
    firmware = await conn.get_text("GET SYSTEM FIRMWARE")
    serial = await conn.get_text("GET SYSTEM SERIALNUMBER")
    if firmware is None or serial is None:
        raise GhlOutdated("SYSTEM-Befehle fehlen, mindestens Firmware 7.52 nötig")
    return firmware, serial


async def discover(conn: GhlConnection) -> Layout:
    firmware, serial = await read_identity(conn)
    layout = Layout(firmware=firmware, serial=serial)

    for i in range(MAX_SENSORS):
        if await conn.get_float(f"GET SENSOR[{i}] ACTVALUE") is None:
            break
        layout.sensors[i] = await conn.get_text(f"GET SENSOR[{i}] DESCRIPTION") or ""

    # Unbenutzte Einträge haben keinen Namen; nach einer Reihe davon ist Schluss.
    unnamed = 0
    for i in range(MAX_CHANNELS):
        name = await conn.get_text(f"GET SWITCHCHANNEL[{i}] DESCRIPTION")
        if name is None:
            break
        if name:
            unnamed = 0
            current = await conn.get_float(f"GET SWITCHCHANNEL[{i}] ACTCURRENT")
            layout.channels[i] = ChannelInfo(name, current is not None)
        else:
            unnamed += 1
            if unnamed >= MAX_UNNAMED_RUN:
                break

    unnamed = 0
    for i in range(MAX_DOSERS):
        name = await conn.get_text(f"GET DOSER[{i}] DESCRIPTION")
        if name is None:
            break
        if name:
            unnamed = 0
            capacity = await conn.get_float(f"GET DOSER[{i}] CAPACITY")
            layout.dosers[i] = DoserInfo(name, capacity or 0.0)
        else:
            unnamed += 1
            if unnamed >= MAX_UNNAMED_RUN:
                break

    for i in range(MAX_LEVELS):
        if await conn.get_float(f"GET LEVELSENSOR[{i}] ACTSTATE") is None:
            break
        layout.levels[i] = await conn.get_text(f"GET LEVELSENSOR[{i}] DESCRIPTION") or ""

    return layout


async def poll(conn: GhlConnection, layout: Layout) -> dict[str, Any]:
    """Alle aktuellen Werte; fehlende Werte sind None."""
    data: dict[str, Any] = {
        "sensors": {},
        "channels": {},
        "dosers": {},
        "levels": {},
        "kh": None,
    }
    for i in layout.sensors:
        data["sensors"][i] = await conn.get_float(f"GET SENSOR[{i}] ACTVALUE")

    for i, channel in layout.channels.items():
        state = await conn.get_float(f"GET SWITCHCHANNEL[{i}] ACTSTATE")
        current = None
        if channel.has_current:
            current = await conn.get_float(f"GET SWITCHCHANNEL[{i}] ACTCURRENT")
        data["channels"][i] = {
            "on": None if state is None else state >= 0.5,
            "current": current,
        }

    for i in layout.dosers:
        data["dosers"][i] = await conn.get_float(f"GET DOSER[{i}] FILLLEVEL")

    for i in layout.levels:
        state = await conn.get_float(f"GET LEVELSENSOR[{i}] ACTSTATE")
        data["levels"][i] = None if state is None else state >= 0.5

    # Der KH Director antwortet mit NACK (-101), solange er nicht aktiv ist.
    data["kh"] = await conn.get_float("GET KHDIRECTOR ACTVALUE")
    return data
