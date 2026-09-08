"""Number entities for the iCSee Feeder integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAX_SERVINGS, MIN_SERVINGS
from .coordinator import IcseeFeederCoordinator
from .entity import IcseeFeederEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iCSee feeder number entities."""

    coordinator: IcseeFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IcseeFeederPortionsNumber(coordinator)])


class IcseeFeederPortionsNumber(IcseeFeederEntity, NumberEntity):
    """Number entity for the default manual feed portion count."""

    _attr_icon = "mdi:numeric"
    _attr_mode = NumberMode.BOX
    _attr_native_max_value = MAX_SERVINGS
    _attr_native_min_value = MIN_SERVINGS
    _attr_native_step = 1
    _attr_translation_key = "default_servings"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the number."""

        super().__init__(coordinator, "default_servings")

    @property
    def native_value(self) -> int:
        """Return the default serving count."""

        return self.coordinator.default_servings

    async def async_set_native_value(self, value: float) -> None:
        """Set the default serving count."""

        await self.coordinator.async_set_default_servings(int(value))
        self.async_write_ha_state()

