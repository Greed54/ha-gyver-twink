"""GyverTwink UDP protocol: packet encoding and decoding.

Pure Python, no Home Assistant imports, so it can be shared with the emulator
and tested on its own. See docs/protocol.md for the full description.
"""

from __future__ import annotations

from dataclasses import dataclass

PORT = 8888
HEADER = b"GT"

# Stock commands (firmware 1.0-1.2, understood by the GyverTwink app)
CMD_DISCOVER = 0
CMD_SETTINGS = 1
CMD_SET = 2
CMD_CALIBRATION = 3
CMD_EFFECT_PREVIEW = 4

# Extended commands (firmware 1.3, ha-gyver-twink)
CMD_EXT_INFO = 5
CMD_SET_EFFECT = 6
CMD_GET_EFFECT_PARAMS = 7
CMD_SET_EFFECT_PARAMS = 8

# Sub-commands of CMD_SET
SET_LED_COUNT = 0
SET_POWER = 1
SET_BRIGHTNESS = 2
SET_AUTO_SWITCH = 3
SET_RANDOM_ORDER = 4
SET_SWITCH_PERIOD = 5
SET_NEXT_EFFECT = 6
SET_OFF_TIMER = 7
SET_OFF_TIMER_MINUTES = 8

# Sub-commands of CMD_EFFECT_PREVIEW (act on the previewed effect)
PREVIEW_SELECT = 0
PREVIEW_FAVORITE = 1
PREVIEW_SCALE = 2
PREVIEW_SPEED = 3

# Sub-commands of CMD_CALIBRATION
CALIB_START = 0  # clear the strip, enter calibration mode
CALIB_LED = 1  # {1, n/100, n%100, x, y}: store x,y of LED n-1, light LED n
CALIB_FINISH = 2  # save coordinates to EEPROM, leave calibration mode

LED_MAX = 500
SWITCH_PERIOD_MIN = 1
SWITCH_PERIOD_MAX = 10
OFF_TIMER_MIN = 1
OFF_TIMER_MAX = 250

# 11 palettes; effects 0-10 are gradients, 11-21 are Perlin noise.
PALETTES = (
    "party",
    "rainbow",
    "stripe",
    "sunset",
    "pepsi",
    "warm",
    "cold",
    "hot",
    "pink",
    "cyber",
    "red_white",
)
EFFECTS: tuple[str, ...] = tuple(f"{p}_gradient" for p in PALETTES) + tuple(
    f"{p}_noise" for p in PALETTES
)


def packet(*data: int) -> bytes:
    """Build a packet: 'GT' followed by bytes."""
    return HEADER + bytes(v & 0xFF for v in data)


def parse(raw: bytes) -> tuple[int, bytes] | None:
    """Return (code, payload) for a valid reply, payload starts after the code."""
    if len(raw) < 3 or not raw.startswith(HEADER):
        return None
    return raw[2], raw[3:]


@dataclass(slots=True)
class Settings:
    """Reply to CMD_SETTINGS (also pushed by firmware 1.3)."""

    led_count: int
    power: bool
    brightness: int
    auto_switch: bool
    random_order: bool
    switch_period: int
    off_timer: bool
    off_timer_minutes: int

    @classmethod
    def from_payload(cls, p: bytes) -> Settings:
        if len(p) < 9:
            raise ValueError(f"settings payload too short: {p.hex()}")
        return cls(
            led_count=p[0] * 100 + p[1],
            power=bool(p[2]),
            brightness=p[3],
            auto_switch=bool(p[4]),
            random_order=bool(p[5]),
            switch_period=p[6],
            off_timer=bool(p[7]),
            off_timer_minutes=p[8],
        )


@dataclass(slots=True)
class ExtInfo:
    """Reply to CMD_EXT_INFO (firmware 1.3+)."""

    proto: int
    effect: int
    effect_count: int
    mac: str

    @classmethod
    def from_payload(cls, p: bytes) -> ExtInfo:
        if len(p) < 9:
            raise ValueError(f"ext info payload too short: {p.hex()}")
        return cls(
            proto=p[0],
            effect=p[1],
            effect_count=p[2],
            mac=":".join(f"{b:02x}" for b in p[3:9]),
        )


@dataclass(slots=True)
class EffectParams:
    """Reply to CMD_GET_EFFECT_PARAMS / CMD_SET_EFFECT_PARAMS (firmware 1.3+)."""

    index: int
    favorite: bool
    scale: int
    speed: int

    @classmethod
    def from_payload(cls, p: bytes) -> EffectParams:
        if len(p) < 4:
            raise ValueError(f"effect params payload too short: {p.hex()}")
        return cls(index=p[0], favorite=bool(p[1]), scale=p[2], speed=p[3])
