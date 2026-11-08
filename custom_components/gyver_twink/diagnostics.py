"""Diagnostics for GyverTwink."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import GyverTwinkConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GyverTwinkConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {"title": entry.title, "data": dict(entry.data), "unique_id": entry.unique_id},
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "state": asdict(data) if data else None,
    }
