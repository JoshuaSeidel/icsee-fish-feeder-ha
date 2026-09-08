"""Camera entity for the iCSee Feeder integration."""

from __future__ import annotations

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import build_rtsp_url
from .const import (
    CONF_RTSP_CHANNEL,
    CONF_RTSP_PORT,
    CONF_RTSP_STREAM,
    DEFAULT_RTSP_CHANNEL,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_STREAM,
    DOMAIN,
)
from .coordinator import IcseeFeederCoordinator
from .entity import IcseeFeederEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iCSee feeder camera entities."""

    coordinator: IcseeFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IcseeFeederCamera(coordinator)])


class IcseeFeederCamera(IcseeFeederEntity, Camera):
    """RTSP camera stream from the feeder."""

    _attr_is_streaming = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_translation_key = "camera"

    def __init__(self, coordinator: IcseeFeederCoordinator) -> None:
        """Initialize the camera."""

        IcseeFeederEntity.__init__(self, coordinator, "camera")
        Camera.__init__(self)
        self._attr_brand = coordinator.manufacturer
        self._attr_model = coordinator.model

    async def stream_source(self) -> str | None:
        """Return the RTSP stream source."""

        entry = self.coordinator.entry
        return build_rtsp_url(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data.get(CONF_PASSWORD, ""),
            port=int(entry.options.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)),
            channel=int(entry.options.get(CONF_RTSP_CHANNEL, DEFAULT_RTSP_CHANNEL)),
            stream=int(entry.options.get(CONF_RTSP_STREAM, DEFAULT_RTSP_STREAM)),
        )

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return a still image from the RTSP stream."""

        stream_source = await self.stream_source()
        if stream_source is None:
            return None

        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )
