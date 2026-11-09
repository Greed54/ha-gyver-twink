"""Websocket commands used by the GyverTwink setup panel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback

from . import calibration
from .api import GyverTwinkError
from .const import DOMAIN
from .coordinator import GyverTwinkCoordinator
from .protocol import EFFECTS, LED_MAX, EffectParams

ENTRY_ID = "entry_id"
BYTE = vol.All(vol.Coerce(int), vol.Range(0, 255))
EFFECT_INDEX = vol.All(vol.Coerce(int), vol.Range(0, len(EFFECTS) - 1))
LED_INDEX = vol.All(vol.Coerce(int), vol.Range(0, LED_MAX))

Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any], GyverTwinkCoordinator],
    Awaitable[Any],
]


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_garlands,
        ws_effects_get,
        ws_effects_preview,
        ws_effects_set,
        ws_led_count_set,
        ws_calibration_get,
        ws_calibration_start,
        ws_calibration_led,
        ws_calibration_save,
        ws_calibration_cancel,
        ws_calibration_restore,
    ):
        websocket_api.async_register_command(hass, command)


def _with_garland(handler: Handler):
    """Resolve entry_id to a loaded garland and turn errors into ws errors."""

    @wraps(handler)
    async def wrapper(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> None:
        entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
        if entry is None or entry.domain != DOMAIN:
            connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown garland")
            return
        if entry.state is not ConfigEntryState.LOADED:
            connection.send_error(msg["id"], "not_loaded", "The garland is not connected")
            return
        try:
            result = await handler(hass, connection, msg, entry.runtime_data)
        except GyverTwinkError as err:
            connection.send_error(msg["id"], "garland_error", str(err))
            return
        connection.send_result(msg["id"], result)

    return wrapper


def _params(p: EffectParams | None) -> dict[str, Any] | None:
    return asdict(p) if p else None


def _garland_info(entry) -> dict[str, Any]:
    info: dict[str, Any] = {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "host": entry.data.get(CONF_HOST),
        "connected": entry.state is ConfigEntryState.LOADED,
    }
    if info["connected"]:
        data = entry.runtime_data.data
        info |= {
            "led_count": data.settings.led_count,
            "extended": data.extended,
            "mac": data.ext.mac if data.ext else None,
            "effect": data.ext.effect if data.ext else None,
        }
    return info


@websocket_api.websocket_command({vol.Required("type"): "gyver_twink/garlands"})
@websocket_api.async_response
async def ws_garlands(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    garlands = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        info = _garland_info(entry)
        stored = await calibration.async_load_map(hass, entry.entry_id)
        info["calibration"] = calibration.describe(stored)
        garlands.append(info)
    connection.send_result(msg["id"], {"garlands": garlands, "effects": list(EFFECTS)})


@websocket_api.websocket_command(
    {vol.Required("type"): "gyver_twink/effects/get", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
@_with_garland
async def ws_effects_get(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Parameters of all effects; stock firmware can only show them one by one."""
    if not coordinator.data.extended:
        return {"params": None}
    client = coordinator.client
    return {"params": [_params(await client.get_effect_params(i)) for i in range(len(EFFECTS))]}


@websocket_api.websocket_command(
    {
        vol.Required("type"): "gyver_twink/effects/preview",
        vol.Required(ENTRY_ID): str,
        vol.Required("index"): EFFECT_INDEX,
    }
)
@websocket_api.async_response
@_with_garland
async def ws_effects_preview(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Show an effect for 30 seconds; returns its parameters."""
    return _params(await coordinator.client.preview_effect(msg["index"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "gyver_twink/effects/set",
        vol.Required(ENTRY_ID): str,
        vol.Required("index"): EFFECT_INDEX,
        vol.Required("favorite"): bool,
        vol.Required("scale"): BYTE,
        vol.Required("speed"): BYTE,
    }
)
@websocket_api.async_response
@_with_garland
async def ws_effects_set(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    client = coordinator.client
    args = (msg["index"], msg["favorite"], msg["scale"], msg["speed"])
    if coordinator.data.extended:
        result = await client.set_effect_params(*args)
    else:
        result = await client.set_previewed_effect_params(*args)
    data = coordinator.data
    if data.ext and data.ext.effect == result.index:
        coordinator.async_set_updated_data(replace(data, effect_params=result))
    return _params(result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "gyver_twink/led_count/set",
        vol.Required(ENTRY_ID): str,
        vol.Required("count"): vol.All(vol.Coerce(int), vol.Range(1, LED_MAX)),
    }
)
@websocket_api.async_response
@_with_garland
async def ws_led_count_set(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    await coordinator.client.set_led_count(msg["count"])
    coordinator.async_set_optimistic(led_count=msg["count"])
    await coordinator.async_request_refresh()
    return {"led_count": msg["count"]}


# ---------------- calibration ----------------


@websocket_api.websocket_command(
    {vol.Required("type"): "gyver_twink/calibration/get", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
async def ws_calibration_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    stored = await calibration.async_load_map(hass, msg[ENTRY_ID])
    connection.send_result(msg["id"], calibration.describe(stored))


@websocket_api.websocket_command(
    {vol.Required("type"): "gyver_twink/calibration/start", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
@_with_garland
async def ws_calibration_start(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Clear the strip and enter calibration mode."""
    await coordinator.client.calibration_start()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "gyver_twink/calibration/led",
        vol.Required(ENTRY_ID): str,
        vol.Required("index"): LED_INDEX,
        vol.Optional("x", default=0): BYTE,
        vol.Optional("y", default=0): BYTE,
    }
)
@websocket_api.async_response
@_with_garland
async def ws_calibration_led(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Light LED index (storing x, y for LED index-1)."""
    await coordinator.client.calibration_led(msg["index"], msg["x"], msg["y"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "gyver_twink/calibration/save",
        vol.Required(ENTRY_ID): str,
        vol.Required("points"): vol.All([vol.ExactSequence([BYTE, BYTE])], vol.Length(1, LED_MAX)),
        vol.Required("grid"): vol.ExactSequence([BYTE, BYTE]),
        vol.Optional("missed", default=[]): [LED_INDEX],
    }
)
@websocket_api.async_response
@_with_garland
async def ws_calibration_save(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Write the whole map to the garland, then keep a copy in HA."""
    points = [list(p) for p in msg["points"]]
    await calibration.async_upload_map(coordinator.client, points)
    stored = await calibration.async_save_map(
        hass, msg[ENTRY_ID], points, list(msg["grid"]), msg["missed"]
    )
    return calibration.describe(stored)


@websocket_api.websocket_command(
    {vol.Required("type"): "gyver_twink/calibration/cancel", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
@_with_garland
async def ws_calibration_cancel(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Leave calibration mode, restoring the map saved in HA if there is one.

    The firmware saves whatever it has on leaving calibration mode, so
    without a saved map the LEDs measured so far stay in the garland.
    """
    stored = await calibration.async_load_map(hass, msg[ENTRY_ID])
    if stored:
        await calibration.async_upload_map(coordinator.client, stored["points"])
    else:
        await coordinator.client.calibration_finish()
    return {"restored": bool(stored)}


@websocket_api.websocket_command(
    {vol.Required("type"): "gyver_twink/calibration/restore", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
@_with_garland
async def ws_calibration_restore(hass, connection, msg, coordinator: GyverTwinkCoordinator):
    """Write the map saved in HA back to the garland."""
    stored = await calibration.async_load_map(hass, msg[ENTRY_ID])
    if not stored:
        raise GyverTwinkError("No calibration saved in Home Assistant")
    await calibration.async_upload_map(coordinator.client, stored["points"])
    return calibration.describe(stored)
