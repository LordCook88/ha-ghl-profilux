"""Gemeinsame Basis aller Entities."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import GhlCoordinator


class GhlEntity(CoordinatorEntity[GhlCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GhlCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.layout.serial}_{key}"
        self._attr_name = name
        self._attr_device_info = coordinator.device_info
