"""Integration actions."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .api import GyverTwinkError
from .const import ATTR_EFFECT, ATTR_FAVORITE, ATTR_SCALE, ATTR_SPEED, DOMAIN
from .coordinator import GyverTwinkCoordinator
from .protocol import EFFECTS
from .switch import async_write_effect_params

SERVICE_SET_EFFECT_PARAMS = "set_effect_params"

SET_EFFECT_PARAMS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_EFFECT): vol.In(EFFECTS),
        vol.Optional(ATTR_SPEED): vol.All(vol.Coerce(int), vol.Range(0, 255)),
        vol.Optional(ATTR_SCALE): vol.All(vol.Coerce(int), vol.Range(0, 255)),
        vol.Optional(ATTR_FAVORITE): cv.boolean,
    }
)


def _coordinators(hass: HomeAssistant, entity_ids: list[str]) -> list[GyverTwinkCoordinator]:
    registry = er.async_get(hass)
    result: list[GyverTwinkCoordinator] = []
    for entity_id in entity_ids:
        ent = registry.async_get(entity_id)
        if ent is None or ent.platform != DOMAIN or ent.config_entry_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_gyver_twink",
                translation_placeholders={"entity_id": entity_id},
            )
        entry = hass.config_entries.async_get_entry(ent.config_entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"entity_id": entity_id},
            )
        result.append(entry.runtime_data)
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def set_effect_params(call: ServiceCall) -> None:
        changes = {
            k: call.data[k] for k in (ATTR_SPEED, ATTR_SCALE, ATTR_FAVORITE) if k in call.data
        }
        for coordinator in _coordinators(hass, call.data[ATTR_ENTITY_ID]):
            if not coordinator.data.extended:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="needs_firmware_13"
                )
            index = (
                EFFECTS.index(call.data[ATTR_EFFECT])
                if ATTR_EFFECT in call.data
                else coordinator.data.ext.effect
            )
            try:
                await async_write_effect_params(coordinator, index, **changes)
            except GyverTwinkError as err:
                raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN, SERVICE_SET_EFFECT_PARAMS, set_effect_params, SET_EFFECT_PARAMS_SCHEMA
    )
