"""Holt alle Werte des ProfiLux in einer Abfragerunde."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GhlAccessError, GhlClient, GhlError, Layout, discover, poll
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GhlCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    layout: Layout

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GhlClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._layout: Layout | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.layout.serial)},
            manufacturer="GHL",
            model="ProfiLux",
            name=f"ProfiLux {self.layout.serial}",
            sw_version=self.layout.firmware,
            configuration_url=f"http://{self.client.host}",
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self.client.connection() as conn:
                if self._layout is None:
                    self._layout = await discover(conn)
                    self.layout = self._layout
                return await poll(conn, self._layout)
        except GhlAccessError as err:
            raise UpdateFailed(
                "Die GHL-API ist am Gerät ausgeschaltet (System → GHL API)"
            ) from err
        except GhlError as err:
            raise UpdateFailed(str(err)) from err
