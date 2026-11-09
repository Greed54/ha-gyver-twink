"""Async UDP client for GyverTwink garlands."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
import logging
import time

from .protocol import (
    CALIB_FINISH,
    CALIB_LED,
    CALIB_START,
    CMD_CALIBRATION,
    CMD_DISCOVER,
    CMD_EFFECT_PREVIEW,
    CMD_EXT_INFO,
    CMD_GET_EFFECT_PARAMS,
    CMD_SET,
    CMD_SET_EFFECT,
    CMD_SET_EFFECT_PARAMS,
    CMD_SETTINGS,
    PORT,
    PREVIEW_FAVORITE,
    PREVIEW_SCALE,
    PREVIEW_SELECT,
    PREVIEW_SPEED,
    SET_LED_COUNT,
    SET_NEXT_EFFECT,
    EffectParams,
    ExtInfo,
    Settings,
    packet,
    parse,
)

_LOGGER = logging.getLogger(__name__)

# Firmware drops packets that arrive less than 50 ms after the previous one
# (stock firmware drops any packet, 1.3 only repeats of the same command).
MIN_GAP = 0.06
DEFAULT_TIMEOUT = 1.0
DEFAULT_RETRIES = 3

PushCallback = Callable[[int, bytes], None]


class GyverTwinkError(Exception):
    """Base error."""


class GyverTwinkTimeout(GyverTwinkError):
    """The garland did not answer."""


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, on_packet: Callable[[bytes, tuple[str, int]], None]) -> None:
        self._on_packet = on_packet

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._on_packet(data, addr)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error: %s", exc)


class GyverTwinkClient:
    """One garland, one UDP socket, strictly serialized requests."""

    def __init__(self, host: str, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._lock = asyncio.Lock()
        self._last_send = 0.0
        self._waiter: (
            tuple[int, Callable[[bytes], bool] | None, asyncio.Future[bytes]] | None
        ) = None
        self._push_cb: PushCallback | None = None

    async def connect(self) -> None:
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self._on_packet), local_addr=("0.0.0.0", 0)
        )

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def set_push_callback(self, cb: PushCallback | None) -> None:
        self._push_cb = cb

    def _on_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr[0] != self.host:
            return
        parsed = parse(data)
        if parsed is None:
            return
        code, payload = parsed
        _LOGGER.debug("%s <- %s", self.host, data[2:].hex(" "))
        if self._waiter:
            want, match, fut = self._waiter
            # Firmware 1.3 pushes use the same codes as replies; a push with
            # stale data must not be taken as the answer to our command.
            if code == want and not fut.done() and (match is None or match(payload)):
                fut.set_result(payload)
                return
        if self._push_cb:
            self._push_cb(code, payload)

    async def _send_raw(self, data: bytes) -> None:
        await self.connect()
        assert self._transport is not None
        wait = self._last_send + MIN_GAP - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _LOGGER.debug("%s -> %s", self.host, data[2:].hex(" "))
        self._transport.sendto(data, (self.host, self.port))
        self._last_send = time.monotonic()

    async def send(self, *data: int) -> None:
        """Fire-and-forget command."""
        async with self._lock:
            await self._send_raw(packet(*data))

    async def request(
        self,
        *data: int,
        reply: int,
        match: Callable[[bytes], bool] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> bytes:
        """Send a command and wait for a reply with the given code."""
        async with self._lock:
            loop = asyncio.get_running_loop()
            for attempt in range(retries):
                fut: asyncio.Future[bytes] = loop.create_future()
                self._waiter = (reply, match, fut)
                try:
                    await self._send_raw(packet(*data))
                    return await asyncio.wait_for(fut, timeout)
                except TimeoutError:
                    _LOGGER.debug(
                        "%s: no reply to %s (attempt %d)", self.host, data, attempt + 1
                    )
                finally:
                    self._waiter = None
            raise GyverTwinkTimeout(f"{self.host} did not reply to command {data[0]}")

    # ---------- high level ----------

    async def get_settings(self, subscribe: bool = False) -> Settings:
        args = (CMD_SETTINGS, 1) if subscribe else (CMD_SETTINGS,)
        return Settings.from_payload(await self.request(*args, reply=CMD_SETTINGS))

    async def get_ext_info(self, retries: int = DEFAULT_RETRIES) -> ExtInfo | None:
        """Extended info, or None on stock firmware (it does not answer)."""
        try:
            payload = await self.request(
                CMD_EXT_INFO, reply=CMD_EXT_INFO, retries=retries
            )
        except GyverTwinkTimeout:
            return None
        return ExtInfo.from_payload(payload)

    async def set_value(self, sub: int, *values: int) -> None:
        await self.send(CMD_SET, sub, *values)

    async def next_effect(self) -> None:
        await self.send(CMD_SET, SET_NEXT_EFFECT)

    async def set_effect(self, index: int) -> ExtInfo:
        """Firmware 1.3: switch to an effect permanently."""
        payload = await self.request(
            CMD_SET_EFFECT,
            index,
            reply=CMD_EXT_INFO,
            match=lambda p: len(p) > 1 and p[1] == index,
        )
        return ExtInfo.from_payload(payload)

    async def preview_effect(self, index: int) -> EffectParams:
        """Stock firmware: show an effect for 30 seconds."""
        payload = await self.request(
            CMD_EFFECT_PREVIEW, PREVIEW_SELECT, index, reply=CMD_EFFECT_PREVIEW
        )
        return EffectParams.from_payload(bytes([index]) + payload)

    async def set_previewed_effect_params(
        self, index: int, favorite: bool, scale: int, speed: int
    ) -> EffectParams:
        """Stock firmware: write parameters through the 30 s preview."""
        await self.preview_effect(index)
        await self.send(CMD_EFFECT_PREVIEW, PREVIEW_FAVORITE, int(favorite))
        await self.send(CMD_EFFECT_PREVIEW, PREVIEW_SCALE, scale)
        await self.send(CMD_EFFECT_PREVIEW, PREVIEW_SPEED, speed)
        return EffectParams(index, favorite, scale, speed)

    async def set_led_count(self, count: int) -> None:
        await self.send(CMD_SET, SET_LED_COUNT, count // 100, count % 100)

    # Calibration (no replies, the garland just shows the LED)

    async def calibration_start(self) -> None:
        await self.send(CMD_CALIBRATION, CALIB_START)

    async def calibration_led(self, index: int, x: int, y: int) -> None:
        """Store x,y for LED index-1 and light LED index."""
        await self.send(CMD_CALIBRATION, CALIB_LED, index // 100, index % 100, x, y)

    async def calibration_finish(self) -> None:
        await self.send(CMD_CALIBRATION, CALIB_FINISH)

    async def get_effect_params(self, index: int) -> EffectParams:
        payload = await self.request(
            CMD_GET_EFFECT_PARAMS,
            index,
            reply=CMD_GET_EFFECT_PARAMS,
            match=lambda p: len(p) > 0 and p[0] == index,
        )
        return EffectParams.from_payload(payload)

    async def set_effect_params(
        self, index: int, favorite: bool, scale: int, speed: int
    ) -> EffectParams:
        payload = await self.request(
            CMD_SET_EFFECT_PARAMS,
            index,
            int(favorite),
            scale,
            speed,
            reply=CMD_GET_EFFECT_PARAMS,
            match=lambda p: len(p) > 0 and p[0] == index,
        )
        return EffectParams.from_payload(payload)


async def async_discover(
    broadcasts: Iterable[str], timeout: float = 2.5, port: int = PORT
) -> list[str]:
    """Broadcast a discovery packet and collect answering IPs.

    The firmware delays its answer by (last octet * 2) ms, up to ~0.5 s.
    """
    found: list[str] = []

    def on_packet(data: bytes, addr: tuple[str, int]) -> None:
        parsed = parse(data)
        if parsed and parsed[0] == CMD_DISCOVER and addr[0] not in found:
            found.append(addr[0])

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Protocol(on_packet), local_addr=("0.0.0.0", 0), allow_broadcast=True
    )
    try:
        for bcast in broadcasts:
            try:
                transport.sendto(packet(CMD_DISCOVER), (bcast, port))
            except OSError as err:
                _LOGGER.debug("Discovery to %s failed: %s", bcast, err)
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return sorted(found, key=lambda ip: tuple(int(x) for x in ip.split(".")))
