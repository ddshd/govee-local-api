from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .govee_local_api import GoveeController, GoveeDevice
from .govee_local_api.light_capabilities import GoveeLightFeatures

_LOGGER = logging.getLogger(__name__)

MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 9000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: GoveeController = hass.data[DOMAIN][entry.entry_id]["controller"]

    @callback
    def _on_device_discovered(device: GoveeDevice, is_new: bool) -> bool:
        if is_new:
            async_add_entities([GoveeLightEntity(device)])
        return True

    controller.set_device_discovered_callback(_on_device_discovered)

    if controller.devices:
        async_add_entities([GoveeLightEntity(d) for d in controller.devices])


class GoveeLightEntity(LightEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN

    def __init__(self, device: GoveeDevice) -> None:
        self._device = device
        self._attr_unique_id = device.fingerprint
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.fingerprint)},
            name=f"Govee {device.sku}",
            model=device.sku,
            manufacturer="Govee",
        )
        self._build_capability_attrs()

    def _build_capability_attrs(self) -> None:
        features = self._device.capabilities.features
        modes: set[ColorMode] = set()

        if features & GoveeLightFeatures.COLOR_RGB:
            modes.add(ColorMode.RGB)
        if features & GoveeLightFeatures.COLOR_KELVIN_TEMPERATURE:
            modes.add(ColorMode.COLOR_TEMP)
        if not modes and features & GoveeLightFeatures.BRIGHTNESS:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = modes

        if features & GoveeLightFeatures.SCENES:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = self._device.capabilities.available_scenes
        else:
            self._attr_supported_features = LightEntityFeature(0)
            self._attr_effect_list = None

    # --- State ---

    @property
    def available(self) -> bool:
        return self._device.is_connected

    @property
    def is_on(self) -> bool:
        return self._device.on

    @property
    def brightness(self) -> int | None:
        if not (self._device.capabilities.features & GoveeLightFeatures.BRIGHTNESS):
            return None
        return round(self._device.brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        if ColorMode.RGB not in self._attr_supported_color_modes:
            return None
        return self._device.rgb_color

    @property
    def color_temp_kelvin(self) -> int | None:
        if ColorMode.COLOR_TEMP not in self._attr_supported_color_modes:
            return None
        temp = self._device.temperature_color
        return temp if temp and temp > 0 else None

    @property
    def color_mode(self) -> ColorMode:
        modes = self._attr_supported_color_modes
        if ColorMode.COLOR_TEMP in modes and self._device.temperature_color > 0:
            return ColorMode.COLOR_TEMP
        if ColorMode.RGB in modes:
            return ColorMode.RGB
        return next(iter(modes))

    @property
    def effect(self) -> str | None:
        return None

    # --- Commands ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self._device.on or not kwargs:
            await self._device.turn_on()

        if ATTR_BRIGHTNESS in kwargs:
            pct = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await self._device.set_brightness(max(1, pct))

        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            await self._device.set_rgb_color(r, g, b)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self._device.set_temperature(kwargs[ATTR_COLOR_TEMP_KELVIN])

        if ATTR_EFFECT in kwargs:
            await self._device.set_scene(kwargs[ATTR_EFFECT])

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.turn_off()

    # --- HA lifecycle ---

    async def async_added_to_hass(self) -> None:
        self._device.set_update_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        self._device.set_update_callback(None)

    @callback
    def _handle_update(self, _device: GoveeDevice) -> None:
        self.async_write_ha_state()
