"""Calibration maps kept in Home Assistant.

The garland stores LED coordinates in its EEPROM, but it cannot report them
(stock firmware). Keeping a copy in HA lets the panel show the map and write
it back after a reflash or an aborted calibration.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import GyverTwinkClient
from .const import DOMAIN

STORAGE_VERSION = 1


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.calibration.{entry_id}")


async def async_load_map(hass: HomeAssistant, entry_id: str) -> dict[str, Any] | None:
    return await _store(hass, entry_id).async_load()


async def async_save_map(
    hass: HomeAssistant,
    entry_id: str,
    points: list[list[int]],
    grid: list[int],
    missed: list[int],
) -> dict[str, Any]:
    data = {
        "points": points,
        "grid": grid,
        "missed": missed,
        "created": dt_util.utcnow().isoformat(),
    }
    await _store(hass, entry_id).async_save(data)
    return data


async def async_remove_map(hass: HomeAssistant, entry_id: str) -> None:
    await _store(hass, entry_id).async_remove()


async def async_upload_map(client: GyverTwinkClient, points: list[list[int]]) -> None:
    """Write all coordinates to the garland and save them to its EEPROM.

    Firmware stores the coordinates of LED n-1 when asked to light LED n,
    so LED i is written by the command for index i+1. The client keeps a
    60 ms gap between packets: 200 LEDs take about 12 s.
    """
    await client.calibration_start()
    await asyncio.sleep(0.1)
    for i, (x, y) in enumerate(points):
        await client.calibration_led(i + 1, x, y)
    await client.calibration_finish()


def describe(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Stored map as sent to the panel."""
    if not data:
        return None
    created = data.get("created")
    return {
        "points": data["points"],
        "grid": data["grid"],
        "missed": data.get("missed", []),
        "created": created if isinstance(created, str) else None,
    }

