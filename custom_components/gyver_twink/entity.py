"""Base entity for GyverTwink."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GyverTwinkCoordinator


class GyverTwinkEntity(CoordinatorEntity[GyverTwinkCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GyverTwinkCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        ext = coordinator.data.ext if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, ext.mac)} if ext else set(),
            name=entry.title,
            manufacturer="AlexGyver",
            model="GyverTwink",
            sw_version="1.3" if ext else "1.2 (stock)",
            configuration_url="https://github.com/AlexGyver/GyverTwink",
        )

    @property
    def settings(self):
        return self.coordinator.data.settings


class GyverTwinkExtEntity(GyverTwinkEntity):
    """Entity that needs firmware 1.3."""

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.extended
