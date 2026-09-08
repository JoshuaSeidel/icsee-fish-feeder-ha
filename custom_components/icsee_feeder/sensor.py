"""Sensor entities for the iCSee Feeder integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import feed_record_datetime
from .const import (
    ATTR_FEED_TYPE,
    ATTR_NOT_FEEDING,
    ATTR_RAW_RESPONSE,
    ATTR_SERVINGS,
    DOMAIN,
    FEED_TYPE_AUTOMATIC,
    FEED_TYPE_MANUAL,
)
from .coordinator import IcseeFeederCoordinator
from .entity import IcseeFeederEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iCSee feeder sensor entities."""

    coordinator: IcseeFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            IcseeFeederLastFeedSensor(coordinator),
            IcseeFeederLastFeedServingsSensor(coordinator),
            IcseeFeederScheduleCountSensor(coordinator),
            IcseeFeederFeederSupportSensor(coordinator),
        ]
    )


class IcseeFeederLastFeedSensor(IcseeFeederEntity, SensorEntity):
    """Timestamp of the latest known feed."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_feed"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, "last_feed")

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the latest feed."""

        record = self.coordinator.last_feed_record
        if record is None:
            return None
        parsed = feed_record_datetime(record)
        if parsed is None:
            return None
        return parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return metadata about the latest feed."""

        record = self.coordinator.last_feed_record
        if record is None:
            return None

        return {
            ATTR_SERVINGS: record.get("Servings"),
            ATTR_FEED_TYPE: _feed_type_label(record.get("Type")),
        }


class IcseeFeederLastFeedServingsSensor(IcseeFeederEntity, SensorEntity):
    """Portions dispensed during the latest known feed."""

    _attr_icon = "mdi:counter"
    _attr_translation_key = "last_feed_servings"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, "last_feed_servings")

    @property
    def native_value(self) -> int | None:
        """Return latest feed servings."""

        record = self.coordinator.last_feed_record
        if record is None:
            return None
        return _coerce_int(record.get("Servings"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return metadata from the latest manual feed command."""

        result = self.coordinator.last_manual_feed_result
        if result is None:
            return None

        return {
            "requested_servings": result.requested_servings,
            "fed_servings": result.fed_servings,
            ATTR_NOT_FEEDING: result.not_feeding,
            ATTR_RAW_RESPONSE: result.response,
        }


class IcseeFeederScheduleCountSensor(IcseeFeederEntity, SensorEntity):
    """Number of scheduled feed entries on the feeder."""

    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "scheduled_feeds"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, "scheduled_feeds")

    @property
    def native_value(self) -> int:
        """Return enabled schedule count."""

        return sum(1 for entry in self.coordinator.feed_book if entry.get("Enable"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the schedule entries."""

        return {
            "entries": self.coordinator.feed_book,
            "total_entries": len(self.coordinator.feed_book),
        }


class IcseeFeederFeederSupportSensor(IcseeFeederEntity, SensorEntity):
    """Reports whether feeder support was advertised by firmware."""

    _attr_icon = "mdi:information-outline"
    _attr_translation_key = "feeder_support"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, "feeder_support")

    @property
    def native_value(self) -> str:
        """Return feeder support state."""

        if not self.coordinator.data:
            return "unknown"
        support = self.coordinator.data.supports_feeder
        if support is None:
            return "unknown"
        return "supported" if support else "not_supported"


def _feed_type_label(feed_type: Any) -> str | None:
    feed_type = _coerce_int(feed_type)
    if feed_type == FEED_TYPE_AUTOMATIC:
        return "automatic"
    if feed_type == FEED_TYPE_MANUAL:
        return "manual"
    return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
