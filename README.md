# GyverTwink for Home Assistant

Home Assistant integration and extended firmware for
[GyverTwink](https://github.com/AlexGyver/GyverTwink) — the ESP8266 smart
garland with camera calibration by AlexGyver.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greed54&repository=ha-gyver-twink&category=integration)

## Features

| | Stock firmware 1.2 | Firmware 1.3 (this repo) |
|---|:-:|:-:|
| On/off, brightness | ✅ | ✅ |
| Auto switch, random order, period | ✅ | ✅ |
| Off timer | ✅ | ✅ |
| Next effect button | ✅ | ✅ |
| Choose effect | 30 s preview | ✅ permanent |
| Current effect shown | — | ✅ |
| Effect speed / scale / favourite | — | ✅ |
| Instant updates | polling 15 s | ✅ push |
| Zeroconf discovery | — | ✅ |
| OTA updates | — | ✅ |

The integration detects the firmware automatically and switches to the
extended protocol as soon as the garland is reflashed.

## Installation

1. HACS → ⋮ → *Custom repositories* → `https://github.com/greed54/ha-gyver-twink`, category *Integration*.
2. Install **GyverTwink**, restart Home Assistant.
3. *Settings → Devices & services → Add integration → GyverTwink*. The garland
   is found by broadcast; if not, enter its IP.

### Entities

| Entity | |
|---|---|
| `light` | power, brightness, effect |
| `switch` | auto switch, random order, off timer, *current effect in rotation* (1.3) |
| `number` | switch period, off timer minutes, LED count (disabled by default), effect speed / scale (1.3) |
| `button` | next effect |

Action `gyver_twink.set_effect_params` changes speed, scale or favourite of any
effect (firmware 1.3).

## Firmware 1.3

`firmware/GyverTwink_v1.3` is GyverTwink 1.2 with an extended, backwards
compatible UDP protocol ([docs/protocol.md](docs/protocol.md)). The GyverTwink
app, calibration and the button work as before; settings and calibration
stored in EEPROM are kept.

Check `LED_PIN`, `LED_ORDER`, `BTN_PIN` at the top of `GyverTwink_v1.3.ino`
before flashing.

**PlatformIO** (recommended):

```sh
cd firmware
pio run -t upload                 # first time, over USB
pio run -e d1_mini_ota -t upload  # later, over Wi-Fi (set upload_port)
```

**Arduino IDE**: ESP8266 core, board *LOLIN(WEMOS) D1 R2 & mini*, Flash size
*4MB (FS:2MB OTA:~1019KB)*; libraries FastLED 3.4, EEManager, EncButton 1.x,
SimplePortal from the library manager. Open `GyverTwink_v1.3/GyverTwink_v1.3.ino`.

CI builds `firmware.bin` on every push (Actions → Validate → artifacts).

## Testing without a garland

```sh
python3 tools/emulator.py          # firmware 1.3
python3 tools/emulator.py --stock  # stock 1.2
```

The emulator listens on UDP 8888 and mirrors the firmware logic, including the
anti-bounce and the stock "no favourites" hang.

## License and credits

- `custom_components/`, `tools/`, `docs/` — MIT, © greed54 (see `LICENSE`).
- `firmware/` — based on [GyverTwink](https://github.com/AlexGyver/GyverTwink)
  by AlexGyver, MIT, © 2021 Alex (see `firmware/LICENSE`). Changes for
  version 1.3 are listed in the header of `GyverTwink_v1.3.ino`.
- `firmware/lib/` — [EEManager](https://github.com/GyverLibs/EEManager),
  [EncButton](https://github.com/GyverLibs/EncButton),
  [SimplePortal](https://github.com/GyverLibs/SimplePortal) by AlexGyver,
  MIT, unmodified, each with its own `LICENSE`.

This project is not affiliated with AlexGyver.
