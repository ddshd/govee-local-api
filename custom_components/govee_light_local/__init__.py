from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_IPS,
    CONF_DISCOVERY,
    CONF_LISTENING_PORT,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)
from .govee_local_api import GoveeController

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    discovery_enabled: bool = entry.data.get(CONF_DISCOVERY, True)
    device_ips: list[str] = entry.data.get(CONF_DEVICE_IPS, [])
    listening_port: int = entry.data.get(CONF_LISTENING_PORT, DEFAULT_LISTENING_PORT)

    controller = GoveeController(
        loop=hass.loop,
        listening_port=listening_port,
        discovery_enabled=discovery_enabled,
        evict_enabled=discovery_enabled,
        logger=_LOGGER,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"controller": controller}

    for ip in device_ips:
        controller.add_device_to_discovery_queue(ip)

    await controller.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        controller: GoveeController = data["controller"]
        cleanup_done = controller.cleanup()
        try:
            await asyncio.wait_for(cleanup_done.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timed out waiting for Govee controller cleanup")
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
