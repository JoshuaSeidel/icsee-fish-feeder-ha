"""Data coordinator for the iCSee Feeder integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IcseeFeederAuthError,
    IcseeFeederClient,
    IcseeFeederConnectionError,
    IcseeFeederError,
    IcseeFeederStatus,
    ManualFeedResult,
    latest_feed_record,
)
from .const import CONF_DEFAULT_SERVINGS, DEFAULT_SERVINGS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class IcseeFeederCoordinator(DataUpdateCoordinator[IcseeFeederStatus]):
    """Coordinator that polls feeder status and serializes control calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: IcseeFeederClient,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self._entry = config_entry
        self.client = client
        self.default_servings = int(
            config_entry.options.get(CONF_DEFAULT_SERVINGS, DEFAULT_SERVINGS)
        )
        self.last_manual_feed_result: ManualFeedResult | None = None
        self._command_lock = asyncio.Lock()

    async def _async_update_data(self) -> IcseeFeederStatus:
        """Fetch status from the feeder."""

        try:
            return await self.hass.async_add_executor_job(self.client.get_status)
        except IcseeFeederAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (IcseeFeederConnectionError, IcseeFeederError) as err:
            raise UpdateFailed(str(err)) from err

    async def async_feed(self, servings: int | None = None) -> ManualFeedResult:
        """Dispense food and refresh coordinator data."""

        feed_servings = int(servings or self.default_servings)
        async with self._command_lock:
            try:
                result = await self.hass.async_add_executor_job(
                    self.client.feed_manual,
                    feed_servings,
                )
            except IcseeFeederAuthError as err:
                raise HomeAssistantError("Invalid iCSee feeder credentials") from err
            except (IcseeFeederError, ValueError) as err:
                raise HomeAssistantError(str(err)) from err

            self.last_manual_feed_result = result
            await self.async_request_refresh()
            return result

    async def async_add_scheduled_feed(self, feed_time: str, servings: int) -> None:
        """Add a scheduled feed entry."""

        async with self._command_lock:
            try:
                await self.hass.async_add_executor_job(
                    self.client.add_scheduled_feed,
                    str(feed_time),
                    int(servings),
                )
            except IcseeFeederAuthError as err:
                raise HomeAssistantError("Invalid iCSee feeder credentials") from err
            except (IcseeFeederError, ValueError) as err:
                raise HomeAssistantError(str(err)) from err

            await self.async_request_refresh()

    async def async_delete_scheduled_feed(
        self,
        feed_time: str,
        servings: int | None = None,
    ) -> None:
        """Delete scheduled feed entries."""

        async with self._command_lock:
            try:
                await self.hass.async_add_executor_job(
                    self.client.delete_scheduled_feed,
                    str(feed_time),
                    servings,
                )
            except IcseeFeederAuthError as err:
                raise HomeAssistantError("Invalid iCSee feeder credentials") from err
            except (IcseeFeederError, ValueError) as err:
                raise HomeAssistantError(str(err)) from err

            await self.async_request_refresh()

    async def async_set_default_servings(self, servings: int) -> None:
        """Persist the default manual-feed serving count."""

        self.default_servings = int(servings)
        options = dict(self._entry.options)
        options[CONF_DEFAULT_SERVINGS] = self.default_servings
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=options,
        )

    def update_options_from_entry(self) -> None:
        """Reload in-memory options from the config entry."""

        self.default_servings = int(
            self._entry.options.get(CONF_DEFAULT_SERVINGS, DEFAULT_SERVINGS)
        )

    @property
    def device_id(self) -> str:
        """Return a stable device identifier."""

        if self.data and self.data.serial:
            return self.data.serial
        return f"{self._entry.data[CONF_HOST]}:{self._entry.data[CONF_PORT]}"

    @property
    def device_name(self) -> str:
        """Return the device display name."""

        return self._entry.title or "iCSee Feeder"

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer display name."""

        return "iCSee / Xiongmai"

    @property
    def model(self) -> str | None:
        """Return the model reported by the device."""

        return self.data.model if self.data else None

    @property
    def software_version(self) -> str | None:
        """Return the software version reported by the device."""

        return self.data.software_version if self.data else None

    @property
    def feed_history(self) -> list[dict[str, Any]]:
        """Return feed history records."""

        return self.data.feed_history if self.data else []

    @property
    def feed_book(self) -> list[dict[str, Any]]:
        """Return scheduled feed records."""

        return self.data.feed_book if self.data else []

    @property
    def last_feed_record(self) -> dict[str, Any] | None:
        """Return the latest known feed record."""

        return latest_feed_record(self.feed_history)


def make_client_from_entry(entry: ConfigEntry) -> IcseeFeederClient:
    """Create an API client from a config entry."""

    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

    return IcseeFeederClient(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data.get(CONF_PASSWORD, ""),
        port=entry.data[CONF_PORT],
    )
