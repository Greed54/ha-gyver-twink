"""Data coordinator for GyverTwink."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GyverTwinkClient, GyverTwinkError
from .const import (
    DOMAIN,
    EXT_PROBE_INTERVAL,
    SCAN_INTERVAL_POLL,
    SCAN_INTERVAL_PUSH,
)
from .protocol import (
    CMD_EXT_INFO,
    CMD_GET_EFFECT_PARAMS,
    CMD_SETTINGS,
    EffectParams,
    ExtInfo,
    Settings,
)

_LOGGER = logging.getLogger(__name__)

type GyverTwinkConfigEntry = ConfigEntry[GyverTwinkCoordinator]


@dataclass(slots=True, frozen=True)
class GarlandState:
    settings: Settings
    ext: ExtInfo | None = None
    effect_params: EffectParams | None = None

    @property
    def extended(self) -> bool:
        return self.ext is not None


class GyverTwinkCoordinator(DataUpdateCoordinator[GarlandState]):
    """Polls the garland and receives pushes from firmware 1.3."""

    config_entry: GyverTwinkConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: GyverTwinkConfigEntry, client: GyverTwinkClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=SCAN_INTERVAL_POLL,
            always_update=False,
        )
        self.client = client
        self._last_probe = 0.0
        self._extended = False
        client.set_push_callback(self._handle_push)

    async def _async_update_data(self) -> GarlandState:
        try:
            settings = await self.client.get_settings(subscribe=True)

            ext: ExtInfo | None = None
            now = time.monotonic()
            if self._extended or now - self._last_probe > EXT_PROBE_INTERVAL.total_seconds():
                self._last_probe = now
                # Stock firmware never answers: probe once, do not retry.
                # Settings answered, so the garland is alive: no answer here
                # means stock firmware (e.g. reflashed back).
                ext = await self.client.get_ext_info(retries=3 if self._extended else 1)

            params: EffectParams | None = None
            if ext is not None:
                params = await self.client.get_effect_params(ext.effect)
        except GyverTwinkError as err:
            raise UpdateFailed(str(err)) from err

        if (ext is not None) != self._extended:
            self._extended = ext is not None
            self.update_interval = (
                SCAN_INTERVAL_PUSH if self._extended else SCAN_INTERVAL_POLL
            )
            _LOGGER.info(
                "%s: firmware %s", self.client.host, "1.3 (push)" if ext else "stock (poll)"
            )
        return GarlandState(settings, ext, params)

    @callback
    def _handle_push(self, code: int, payload: bytes) -> None:
        """Unsolicited packet from firmware 1.3."""
        if self.data is None:
            return
        try:
            if code == CMD_SETTINGS:
                new = replace(self.data, settings=Settings.from_payload(payload))
            elif code == CMD_EXT_INFO:
                ext = ExtInfo.from_payload(payload)
                new = replace(self.data, ext=ext)
                if self.data.ext is None or self.data.ext.effect != ext.effect:
                    self.config_entry.async_create_background_task(
                        self.hass, self._async_refresh_params(ext.effect), "gyver_twink params"
                    )
            elif code == CMD_GET_EFFECT_PARAMS:
                new = replace(self.data, effect_params=EffectParams.from_payload(payload))
            else:
                return
        except ValueError as err:
            _LOGGER.debug("Bad push packet: %s", err)
            return
        self.async_set_updated_data(new)

    async def _async_refresh_params(self, effect: int) -> None:
        try:
            params = await self.client.get_effect_params(effect)
        except GyverTwinkError:
            return
        if self.data and self.data.ext and self.data.ext.effect == params.index:
            self.async_set_updated_data(replace(self.data, effect_params=params))

    @callback
    def async_set_optimistic(self, **changes) -> None:
        """Apply a settings change locally before the garland confirms it."""
        if self.data is None:
            return
        self.async_set_updated_data(
            replace(self.data, settings=replace(self.data.settings, **changes))
        )
