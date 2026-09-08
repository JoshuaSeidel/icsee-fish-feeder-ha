"""Constants for the iCSee Feeder integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "icsee_feeder"

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

DEFAULT_PORT = 34567
DEFAULT_USERNAME = "admin"
DEFAULT_SERVINGS = 1
MIN_SERVINGS = 1
MAX_SERVINGS = 20
DEFAULT_TIMEOUT = 10.0
UPDATE_INTERVAL = timedelta(minutes=5)

CONF_DEFAULT_SERVINGS = "default_servings"
CONF_TIMEOUT = "timeout"

ATTR_SERVINGS = "servings"
ATTR_TIME = "time"
ATTR_FEED_TYPE = "feed_type"
ATTR_NOT_FEEDING = "not_feeding"
ATTR_RAW_RESPONSE = "raw_response"

SERVICE_FEED = "feed"
SERVICE_ADD_SCHEDULED_FEED = "add_scheduled_feed"
SERVICE_DELETE_SCHEDULED_FEED = "delete_scheduled_feed"
DATA_ENTITY_SERVICES_REGISTERED = "entity_services_registered"

FEED_TYPE_AUTOMATIC = 1
FEED_TYPE_MANUAL = 2
