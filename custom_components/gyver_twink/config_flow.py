"""Config flow for GyverTwink."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import GyverTwinkClient, GyverTwinkError, async_discover
from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

MANUAL = "manual"


async def _async_probe(host: str) -> str | None:
    """Check the garland answers; return its MAC if firmware 1.3, else None.

    Raises GyverTwinkError when the garland does not answer at all.
    """
    client = GyverTwinkClient(host)
    try:
        await client.get_settings()
        ext = await client.get_ext_info(retries=2)
    finally:
        client.close()
    return format_mac(ext.mac) if ext else None


class GyverTwinkConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._discovered: list[str] = []
        self._host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the network, then let the user pick or type an address."""
        broadcasts = {
            str(addr) for addr in await network.async_get_ipv4_broadcast_addresses(self.hass)
        }
        try:
            found = await async_discover(broadcasts)
        except OSError as err:
            _LOGGER.debug("Discovery failed: %s", err)
            found = []
        configured = {e.data.get(CONF_HOST) for e in self._async_current_entries()}
        self._discovered = [ip for ip in found if ip not in configured]
        if not self._discovered:
            return await self.async_step_manual()
        return await self.async_step_pick()

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_HOST] == MANUAL:
                return await self.async_step_manual()
            try:
                return await self._async_create(user_input[CONF_HOST], user_input[CONF_NAME])
            except GyverTwinkError:
                return self.async_abort(reason="cannot_connect")
        options = {ip: ip for ip in self._discovered} | {MANUAL: "…"}
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._discovered[0]): vol.In(options),
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._async_create(
                    user_input[CONF_HOST].strip(), user_input[CONF_NAME]
                )
            except GyverTwinkError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def _async_create(self, host: str, name: str) -> ConfigFlowResult:
        """Probe the garland and create the entry; raises GyverTwinkError."""
        self._async_abort_entries_match({CONF_HOST: host})
        mac = await _async_probe(host)
        if mac:
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(title=name, data={CONF_HOST: host})

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Firmware 1.3 announces _gyvertwink._udp."""
        host = discovery_info.host
        try:
            mac = await _async_probe(host)
        except GyverTwinkError:
            return self.async_abort(reason="cannot_connect")
        if mac is None:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        # An entry without MAC (stock firmware) may already point to this host.
        self._async_abort_entries_match({CONF_HOST: host})
        self._host = host
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._host is not None
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME], data={CONF_HOST: self._host}
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=DEFAULT_NAME): str}),
            description_placeholders={"host": self._host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                mac = await _async_probe(host)
            except GyverTwinkError:
                errors["base"] = "cannot_connect"
            else:
                if mac and entry.unique_id and mac != entry.unique_id:
                    return self.async_abort(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=entry.unique_id or mac,
                    data_updates={CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )
