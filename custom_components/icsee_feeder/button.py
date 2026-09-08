"""Button entities for the iCSee Feeder integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_SERVINGS,
    ATTR_TIME,
    DATA_ENTITY_SERVICES_REGISTERED,
    DOMAIN,
    MAX_SERVINGS,
    MIN_SERVINGS,
    SERVICE_ADD_SCHEDULED_FEED,
    SERVICE_DELETE_SCHEDULED_FEED,
    SERVICE_FEED,
)
from .coordinator import IcseeFeederCoordinator
from .entity import IcseeFeederEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iCSee feeder button entities."""

    coordinator: IcseeFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IcseeFeederFeedButton(coordinator)])

    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(DATA_ENTITY_SERVICES_REGISTERED):
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            SERVICE_FEED,
            {
                vol.Optional(ATTR_SERVINGS): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SERVINGS, max=MAX_SERVINGS),
                )
            },
            "async_feed",
        )
        platform.async_register_entity_service(
            SERVICE_ADD_SCHEDULED_FEED,
            {
                vol.Required(ATTR_TIME): vol.Coerce(str),
                vol.Required(ATTR_SERVINGS): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SERVINGS, max=MAX_SERVINGS),
                ),
            },
            "async_add_scheduled_feed",
        )
        platform.async_register_entity_service(
            SERVICE_DELETE_SCHEDULED_FEED,
            {
                vol.Required(ATTR_TIME): vol.Coerce(str),
                vol.Optional(ATTR_SERVINGS): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SERVINGS, max=MAX_SERVINGS),
                ),
            },
            "async_delete_scheduled_feed",
        )
        domain_data[DATA_ENTITY_SERVICES_REGISTERED] = True


class IcseeFeederFeedButton(IcseeFeederEntity, ButtonEntity):
    """Button that triggers a manual feed."""

    _attr_icon = "mdi:fish"
    _attr_translation_key = "feed"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the button."""

        super().__init__(coordinator, "feed")

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.async_feed()

    async def async_feed(self, servings: int | None = None) -> None:
        """Entity service that feeds a specific number of servings."""

        await self.coordinator.async_feed(servings)

    async def async_add_scheduled_feed(self, time: str, servings: int) -> None:
        """Entity service that adds a scheduled feed."""

        await self.coordinator.async_add_scheduled_feed(time, servings)

    async def async_delete_scheduled_feed(
        self,
        time: str,
        servings: int | None = None,
    ) -> None:
        """Entity service that deletes scheduled feeds."""

        await self.coordinator.async_delete_scheduled_feed(time, servings)
