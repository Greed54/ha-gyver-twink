"""Button platform: next effect."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GyverTwinkConfigEntry
from .entity import GyverTwinkEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GyverTwinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([NextEffectButton(entry.runtime_data)])


class NextEffectButton(GyverTwinkEntity, ButtonEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_effect")

    async def async_press(self) -> None:
        await self.coordinator.client.next_effect()
        await self.coordinator.async_request_refresh()
