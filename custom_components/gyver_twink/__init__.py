"""The GyverTwink integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import websocket_api
from .api import GyverTwinkClient
from .calibration import async_remove_map
from .const import DOMAIN
from .coordinator import GyverTwinkConfigEntry, GyverTwinkCoordinator
from .panel import async_setup_panel
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    websocket_api.async_register(hass)
    integration = await async_get_integration(hass, DOMAIN)
    await async_setup_panel(hass, str(integration.version))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GyverTwinkConfigEntry) -> bool:
    client = GyverTwinkClient(entry.data[CONF_HOST])
    coordinator = GyverTwinkCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        client.close()
        raise

    # Entries created before firmware 1.3 (or migrated) have no MAC yet.
    ext = coordinator.data.ext
    if entry.unique_id is None and ext is not None:
        mac = format_mac(ext.mac)
        if not any(e.unique_id == mac for e in hass.config_entries.async_entries(DOMAIN)):
            hass.config_entries.async_update_entry(entry, unique_id=mac)

    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GyverTwinkConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GyverTwinkConfigEntry) -> None:
    """Drop the calibration map kept for this garland."""
    await async_remove_map(hass, entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: GyverTwinkConfigEntry) -> bool:
    """Migrate entries from the old 'UDP Garland' integration (version 1)."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        host = entry.data.get("selected_device") or entry.data.get(CONF_HOST)
        if not host:
            _LOGGER.error("Cannot migrate GyverTwink entry without a host")
            return False
        title = "GyverTwink" if entry.title == "UDP Garland" else entry.title
        hass.config_entries.async_update_entry(
            entry, data={CONF_HOST: host}, title=title, version=2
        )
        _LOGGER.info("Migrated GyverTwink entry %s to version 2", host)
    return True
