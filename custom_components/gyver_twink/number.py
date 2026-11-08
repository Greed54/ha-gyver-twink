"""Number platform: switch period, off timer, LED count, effect speed/scale."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GyverTwinkConfigEntry, GyverTwinkCoordinator
from .entity import GyverTwinkEntity, GyverTwinkExtEntity
from .protocol import (
    LED_MAX,
    OFF_TIMER_MAX,
    OFF_TIMER_MIN,
    SET_LED_COUNT,
    SET_OFF_TIMER_MINUTES,
    SET_SWITCH_PERIOD,
    SWITCH_PERIOD_MAX,
    SWITCH_PERIOD_MIN,
)
from .switch import async_write_effect_params

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SettingNumberDescription(NumberEntityDescription):
    sub: int
    field: str


SETTING_NUMBERS = (
    SettingNumberDescription(
        key="switch_period",
        sub=SET_SWITCH_PERIOD,
        field="switch_period",
        native_min_value=SWITCH_PERIOD_MIN,
        native_max_value=SWITCH_PERIOD_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
    ),
    SettingNumberDescription(
        key="off_timer_minutes",
        sub=SET_OFF_TIMER_MINUTES,
        field="off_timer_minutes",
        native_min_value=OFF_TIMER_MIN,
        native_max_value=OFF_TIMER_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    SettingNumberDescription(
        key="led_count",
        sub=SET_LED_COUNT,
        field="led_count",
        native_min_value=1,
        native_max_value=LED_MAX,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

EFFECT_NUMBERS = (
    NumberEntityDescription(
        key="effect_speed",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="effect_scale",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GyverTwinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [SettingNumber(coordinator, d) for d in SETTING_NUMBERS]
    entities += [EffectNumber(coordinator, d) for d in EFFECT_NUMBERS]
    async_add_entities(entities)


class SettingNumber(GyverTwinkEntity, NumberEntity):
    entity_description: SettingNumberDescription

    def __init__(
        self, coordinator: GyverTwinkCoordinator, description: SettingNumberDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        return getattr(self.settings, self.entity_description.field)

    async def async_set_native_value(self, value: float) -> None:
        d = self.entity_description
        v = int(value)
        if d.sub == SET_LED_COUNT:
            await self.coordinator.client.set_value(d.sub, v // 100, v % 100)
        else:
            await self.coordinator.client.set_value(d.sub, v)
        self.coordinator.async_set_optimistic(**{d.field: v})
        await self.coordinator.async_request_refresh()


class EffectNumber(GyverTwinkExtEntity, NumberEntity):
    """Speed / scale of the current effect (firmware 1.3)."""

    def __init__(
        self, coordinator: GyverTwinkCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._field = description.key.removeprefix("effect_")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.effect_params is not None

    @property
    def native_value(self) -> int | None:
        params = self.coordinator.data.effect_params
        return getattr(params, self._field) if params else None

    async def async_set_native_value(self, value: float) -> None:
        await async_write_effect_params(self.coordinator, **{self._field: int(value)})
