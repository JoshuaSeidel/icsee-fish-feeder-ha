"""Diagnostics support for the iCSee Feeder integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IcseeFeederCoordinator

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator: IcseeFeederCoordinator | None = hass.data[DOMAIN].get(entry.entry_id)
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "status": {
            "system_info": coordinator.data.system_info if coordinator.data else {},
            "capabilities": coordinator.data.capabilities if coordinator.data else {},
            "feed_book_count": len(coordinator.feed_book) if coordinator else 0,
            "feed_history_count": len(coordinator.feed_history) if coordinator else 0,
        }
        if coordinator
        else {},
    }

