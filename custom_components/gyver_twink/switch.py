"""Switch platform: auto switch, random order, off timer, effect favourite."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GarlandState, GyverTwinkConfigEntry, GyverTwinkCoordinator
from .entity import GyverTwinkEntity, GyverTwinkExtEntity
from .protocol import SET_AUTO_SWITCH, SET_OFF_TIMER, SET_RANDOM_ORDER

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SettingSwitchDescription(SwitchEntityDescription):
    sub: int
    field: str


SETTING_SWITCHES = (
    SettingSwitchDescription(key="auto_switch", sub=SET_AUTO_SWITCH, field="auto_switch"),
    SettingSwitchDescription(
        key="random_order", sub=SET_RANDOM_ORDER, field="random_order"
    ),
    SettingSwitchDescription(key="off_timer", sub=SET_OFF_TIMER, field="off_timer"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GyverTwinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        SettingSwitch(coordinator, d) for d in SETTING_SWITCHES
    ]
    entities.append(EffectFavoriteSwitch(coordinator))
    async_add_entities(entities)


class SettingSwitch(GyverTwinkEntity, SwitchEntity):
    entity_description: SettingSwitchDescription

    def __init__(
        self, coordinator: GyverTwinkCoordinator, description: SettingSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return getattr(self.settings, self.entity_description.field)

    async def _async_set(self, value: bool) -> None:
        d = self.entity_description
        await self.coordinator.client.set_value(d.sub, int(value))
        self.coordinator.async_set_optimistic(**{d.field: value})
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class EffectFavoriteSwitch(GyverTwinkExtEntity, SwitchEntity):
    """Whether the current effect takes part in the auto switch rotation."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GyverTwinkCoordinator) -> None:
        super().__init__(coordinator, "effect_favorite")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.effect_params is not None

    @property
    def is_on(self) -> bool | None:
        params = self.coordinator.data.effect_params
        return params.favorite if params else None

    async def _async_set(self, value: bool) -> None:
        await async_write_effect_params(self.coordinator, favorite=value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


async def async_write_effect_params(
    coordinator: GyverTwinkCoordinator, index: int | None = None, **changes: Any
) -> None:
    """Read-modify-write parameters of an effect (firmware 1.3)."""
    data: GarlandState = coordinator.data
    client = coordinator.client
    if index is None:
        index = data.ext.effect
    current = (
        data.effect_params
        if data.effect_params and data.effect_params.index == index
        else await client.get_effect_params(index)
    )
    new = replace(current, **changes)
    result = await client.set_effect_params(index, new.favorite, new.scale, new.speed)
    if coordinator.data.ext and coordinator.data.ext.effect == index:
        coordinator.async_set_updated_data(replace(coordinator.data, effect_params=result))
