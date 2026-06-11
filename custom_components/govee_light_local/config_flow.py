from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_IPS,
    CONF_DISCOVERY,
    CONF_LISTENING_PORT,
    DEFAULT_DISCOVERY,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)

_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): bool,
        vol.Optional(CONF_DEVICE_IPS, default=""): str,
        vol.Optional(
            CONF_LISTENING_PORT, default=DEFAULT_LISTENING_PORT
        ): vol.All(vol.Coerce(int), vol.Range(min=1024, max=65535)),
    }
)


def _parse_ips(raw: str) -> list[str]:
    return [ip.strip() for ip in raw.replace(",", "\n").splitlines() if ip.strip()]


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_DISCOVERY: user_input[CONF_DISCOVERY],
        CONF_DEVICE_IPS: _parse_ips(user_input.get(CONF_DEVICE_IPS, "")),
        CONF_LISTENING_PORT: user_input.get(CONF_LISTENING_PORT, DEFAULT_LISTENING_PORT),
    }


class GoveeLightLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Govee Light Local",
                data=_normalize(user_input),
            )

        return self.async_show_form(step_id="user", data_schema=_CONFIG_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GoveeLightLocalOptionsFlow(config_entry)


class GoveeLightLocalOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=_normalize(user_input))

        current = self._entry.data
        ips_str = ", ".join(current.get(CONF_DEVICE_IPS, []))
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DISCOVERY,
                    default=current.get(CONF_DISCOVERY, DEFAULT_DISCOVERY),
                ): bool,
                vol.Optional(CONF_DEVICE_IPS, default=ips_str): str,
                vol.Optional(
                    CONF_LISTENING_PORT,
                    default=current.get(CONF_LISTENING_PORT, DEFAULT_LISTENING_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1024, max=65535)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
