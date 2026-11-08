"""Light platform: power, brightness and effect."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import GyverTwinkConfigEntry
from .entity import GyverTwinkEntity
from .protocol import EFFECTS, SET_BRIGHTNESS, SET_POWER

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GyverTwinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([GyverTwinkLight(entry.runtime_data)])


class GyverTwinkLight(GyverTwinkEntity, LightEntity):
    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "garland")

    @property
    def is_on(self) -> bool:
        return self.settings.power

    @property
    def brightness(self) -> int:
        return self.settings.brightness

    @property
    def effect(self) -> str | None:
        ext = self.coordinator.data.ext
        if ext is None or ext.effect >= len(EFFECTS):
            return None  # stock firmware does not report the current effect
        return EFFECTS[ext.effect]

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            await client.set_value(SET_BRIGHTNESS, brightness)
            self.coordinator.async_set_optimistic(brightness=brightness)
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            await self._async_set_effect(effect)
        if not self.settings.power:
            await client.set_value(SET_POWER, 1)
            self.coordinator.async_set_optimistic(power=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_value(SET_POWER, 0)
        self.coordinator.async_set_optimistic(power=False)
        await self.coordinator.async_request_refresh()

    async def _async_set_effect(self, effect: str) -> None:
        if effect not in EFFECTS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_effect",
                translation_placeholders={"effect": effect},
            )
        index = EFFECTS.index(effect)
        client = self.coordinator.client
        if self.coordinator.data.extended:
            ext = await client.set_effect(index)
            params = await client.get_effect_params(index)
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, ext=ext, effect_params=params)
            )
        else:
            # Stock firmware: the effect is shown for 30 s, then the
            # garland returns to its favourites rotation.
            await client.preview_effect(index)
