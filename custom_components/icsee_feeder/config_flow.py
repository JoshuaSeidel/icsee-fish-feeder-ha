"""Config flow for the iCSee Feeder integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .api import (
    IcseeFeederAuthError,
    IcseeFeederClient,
    IcseeFeederConnectionError,
    IcseeFeederError,
    IcseeFeederStatus,
    IcseeFeederUnsupportedError,
)
from .const import (
    CONF_DEFAULT_SERVINGS,
    CONF_RTSP_CHANNEL,
    CONF_RTSP_PORT,
    CONF_RTSP_STREAM,
    DEFAULT_PORT,
    DEFAULT_RTSP_CHANNEL,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_STREAM,
    DEFAULT_SERVINGS,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_SERVINGS,
    MIN_SERVINGS,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class NotFeeder(Exception):
    """Error to indicate the target does not support feeder functions."""


async def validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> IcseeFeederStatus:
    """Validate user input allows us to connect."""

    client = IcseeFeederClient(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data.get(CONF_PASSWORD, ""),
        port=data[CONF_PORT],
    )

    try:
        return await hass.async_add_executor_job(client.test_connection)
    except IcseeFeederAuthError as err:
        raise InvalidAuth from err
    except IcseeFeederUnsupportedError as err:
        raise NotFeeder from err
    except IcseeFeederConnectionError as err:
        raise CannotConnect from err
    except IcseeFeederError:
        _LOGGER.exception("Unexpected iCSee feeder setup error")
        raise


class IcseeFeederConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an iCSee Feeder config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return IcseeFeederOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                status = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NotFeeder:
                errors["base"] = "not_feeder"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                unique_id = status.serial or (
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                data = dict(user_input)
                default_servings = data.pop(CONF_DEFAULT_SERVINGS)
                rtsp_port = data.pop(CONF_RTSP_PORT)
                rtsp_channel = data.pop(CONF_RTSP_CHANNEL)
                rtsp_stream = data.pop(CONF_RTSP_STREAM)
                title = (
                    status.model
                    or status.serial
                    or f"iCSee Feeder {user_input[CONF_HOST]}"
                )
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options={
                        CONF_DEFAULT_SERVINGS: default_servings,
                        CONF_RTSP_PORT: rtsp_port,
                        CONF_RTSP_CHANNEL: rtsp_channel,
                        CONF_RTSP_STREAM: rtsp_stream,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )


class IcseeFeederOptionsFlow(config_entries.OptionsFlow):
    """Handle options for iCSee Feeder."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Manage options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(options),
        )


def _schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    suggested = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=suggested.get(CONF_HOST, "")): cv.string,
            vol.Optional(
                CONF_PORT,
                default=suggested.get(CONF_PORT, DEFAULT_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                CONF_USERNAME,
                default=suggested.get(CONF_USERNAME, DEFAULT_USERNAME),
            ): cv.string,
            vol.Optional(
                CONF_PASSWORD,
                default=suggested.get(CONF_PASSWORD, ""),
            ): cv.string,
            vol.Optional(
                CONF_DEFAULT_SERVINGS,
                default=suggested.get(CONF_DEFAULT_SERVINGS, DEFAULT_SERVINGS),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SERVINGS, max=MAX_SERVINGS)),
            vol.Optional(
                CONF_RTSP_PORT,
                default=suggested.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_RTSP_CHANNEL,
                default=suggested.get(CONF_RTSP_CHANNEL, DEFAULT_RTSP_CHANNEL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
            vol.Optional(
                CONF_RTSP_STREAM,
                default=suggested.get(CONF_RTSP_STREAM, DEFAULT_RTSP_STREAM),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
        }
    )


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_DEFAULT_SERVINGS,
                default=options.get(CONF_DEFAULT_SERVINGS, DEFAULT_SERVINGS),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SERVINGS, max=MAX_SERVINGS)),
            vol.Optional(
                CONF_RTSP_PORT,
                default=options.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_RTSP_CHANNEL,
                default=options.get(CONF_RTSP_CHANNEL, DEFAULT_RTSP_CHANNEL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
            vol.Optional(
                CONF_RTSP_STREAM,
                default=options.get(CONF_RTSP_STREAM, DEFAULT_RTSP_STREAM),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
        }
    )
