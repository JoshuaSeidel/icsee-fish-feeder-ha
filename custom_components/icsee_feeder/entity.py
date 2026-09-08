"""Shared entity helpers for the iCSee Feeder integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IcseeFeederCoordinator


class IcseeFeederEntity(CoordinatorEntity[IcseeFeederCoordinator]):
    """Base entity for iCSee feeder entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IcseeFeederCoordinator, suffix: str) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=coordinator.device_name,
            sw_version=coordinator.software_version,
        )

