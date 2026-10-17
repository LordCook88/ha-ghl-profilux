"""Schaltkanäle (nur lesend) und Pegelsensoren."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GhlCoordinator
from .entity import GhlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GhlCoordinator = entry.runtime_data
    layout = coordinator.layout
    entities: list[BinarySensorEntity] = []

    for index, channel in layout.channels.items():
        entities.append(GhlChannelState(coordinator, index, channel.name))
    for index, name in layout.levels.items():
        entities.append(GhlLevelSensor(coordinator, index, name))

    async_add_entities(entities)


class GhlChannelState(GhlEntity, BinarySensorEntity):
    """Ob ein Schaltkanal gerade eingeschaltet ist. Schalten kann die API nicht."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: GhlCoordinator, index: int, name: str) -> None:
        super().__init__(coordinator, f"channel_{index}_state", name)
        self._index = index

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data["channels"][self._index]["on"]


class GhlLevelSensor(GhlEntity, BinarySensorEntity):
    """Pegelschalter; an = Zustand 1 laut Gerät."""

    _attr_icon = "mdi:water-check"

    def __init__(self, coordinator: GhlCoordinator, index: int, name: str) -> None:
        super().__init__(coordinator, f"level_{index}", name or f"Pegel {index + 1}")
        self._index = index
        # Nur ein Pegelsensor ist angeschlossen; welcher, ist noch offen.
        self._attr_entity_registry_enabled_default = index == 0

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data["levels"].get(self._index)
