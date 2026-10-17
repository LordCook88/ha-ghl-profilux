"""Messwerte, Ströme, Dosierer-Füllstände und KH Director."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GhlCoordinator
from .entity import GhlEntity

# Die API kennt den Sensortyp nicht. Die Zuordnung gilt für diesen Aufbau:
# 0 Temperatur, 1 pH, 2 Redox, 3 Leitwert (inaktiv, deshalb aus).
# Index: (Name, Geräteklasse, Einheit, aktiv, Nachkommastellen)
SENSOR_DEFAULTS = {
    0: ("Temperatur", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, True, 2),
    1: ("pH", SensorDeviceClass.PH, None, True, 2),
    2: ("Redox", None, "mV", True, 0),
    3: ("Leitwert", SensorDeviceClass.CONDUCTIVITY, "mS/cm", False, 1),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GhlCoordinator = entry.runtime_data
    layout = coordinator.layout
    entities: list[SensorEntity] = []

    for index, name in layout.sensors.items():
        entities.append(GhlMeasurement(coordinator, index, name))
    for index, channel in layout.channels.items():
        if channel.has_current:
            entities.append(GhlChannelCurrent(coordinator, index, channel.name))
    for index, doser in layout.dosers.items():
        entities.append(GhlDoserLevel(coordinator, index, doser.name, doser.capacity))
    entities.append(GhlKhValue(coordinator))

    async_add_entities(entities)


class GhlMeasurement(GhlEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GhlCoordinator, index: int, device_name: str) -> None:
        default = SENSOR_DEFAULTS.get(
            index, (f"Sensor {index + 1}", None, None, True, None)
        )
        name, device_class, unit, enabled, precision = default
        super().__init__(coordinator, f"sensor_{index}", device_name or name)
        self._index = index
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_registry_enabled_default = enabled
        if precision is not None:
            self._attr_suggested_display_precision = precision

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data["sensors"].get(self._index)


class GhlChannelCurrent(GhlEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: GhlCoordinator, index: int, name: str) -> None:
        super().__init__(coordinator, f"channel_{index}_current", f"{name} Strom")
        self._index = index

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data["channels"][self._index]["current"]


class GhlDoserLevel(GhlEntity, SensorEntity):
    """Füllstand des Dosierbehälters in ml; Kapazität als Attribut."""

    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flask-outline"
    _attr_suggested_display_precision = 0

    def __init__(
        self, coordinator: GhlCoordinator, index: int, name: str, capacity: float
    ) -> None:
        super().__init__(coordinator, f"doser_{index}_fill", f"{name} Füllstand")
        self._index = index
        self._capacity = capacity

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data["dosers"].get(self._index)

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        level = self.native_value
        percent = None
        if level is not None and self._capacity > 0:
            percent = round(level / self._capacity * 100, 1)
        return {"kapazitaet_ml": self._capacity, "fuellstand_prozent": percent}


class GhlKhValue(GhlEntity, SensorEntity):
    """Letzter KH-Wert; nicht verfügbar, solange der KH Director nicht antwortet."""

    _attr_native_unit_of_measurement = "dKH"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:test-tube"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: GhlCoordinator) -> None:
        super().__init__(coordinator, "khdirector_kh", "KH Director KH")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data["kh"]

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data["kh"] is not None
