"""Sidebar panel for setting up GyverTwink garlands (calibration, effects)."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL_PATH = "gyver-twink"
PANEL_TITLE = "GyverTwink"
PANEL_ICON = "mdi:pine-tree"
WEBCOMPONENT = "gyver-twink-panel"
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup_panel(hass: HomeAssistant, version: str) -> None:
    """Serve the panel files and add the panel to the sidebar (once)."""
    if PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        return
    # Versioned path: the panel's relative ES module imports inherit it, so
    # an update never mixes old cached modules with new ones.
    base_url = f"{STATIC_URL}/{version}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(base_url, str(FRONTEND_DIR), cache_headers=True)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{base_url}/{WEBCOMPONENT}.js",
        require_admin=False,
        # The toolbar pads itself for the iPhone notch (styles.js).
        handle_safe_area=True,
    )
