# GyverTwink UDP protocol

UDP, port **8888**. Every packet in both directions starts with `'G','T'`
(`0x47 0x54`), followed by bytes `0..255`. Below only the bytes after `GT`
are shown.

> The GyverTwink app (Android / PC) crashes on replies longer than **10 data
> bytes**, so no reply is longer than that, and replies to stock commands
> are unchanged.

> **Anti-bounce.** Stock firmware drops *any* packet that arrives less than
> 50 ms after the previous one. Firmware 1.3 drops only a repeat of the same
> command + sub-command (slider spam). Clients should keep ≥ 60 ms between
> packets to work with both.

## Stock commands (1.0 – 1.2, unchanged in 1.3)

| Request | Meaning | Reply |
|---|---|---|
| `0` | discovery (broadcast) | `0, ip` — last octet of the garland IP (delayed by `ip*2` ms) |
| `1` | read settings | `1, leds/100, leds%100, power, brightness, auto, random, period, off_timer, off_minutes` |
| `2, 0, n/100, n%100` | LED count | — |
| `2, 1, v` | power 0/1 | — |
| `2, 2, v` | brightness 0–255 | — |
| `2, 3, v` | auto switch effects 0/1 | — |
| `2, 4, v` | random order 0/1 | — |
| `2, 5, v` | switch period, minutes | — |
| `2, 6` | next effect | — |
| `2, 7, v` | off timer 0/1 | — |
| `2, 8, v` | off timer, minutes | — |
| `3, …` | camera calibration (app only) | — |
| `4, 0, n` | **preview** effect `n` for 30 s, then the garland moves to the next favourite | `4, fav, scale, speed` |
| `4, 1, v` / `4, 2, v` / `4, 3, v` | favourite / scale / speed of the previewed effect | — |

## Extended commands (1.3)

| Request | Meaning | Reply |
|---|---|---|
| `1, 1` | read settings **and subscribe** to pushes (stock firmware ignores the `1`) | same as `1` |
| `5` | extended info | `5, proto, effect, effect_count, mac[6]` |
| `6, n` | set effect `n` **permanently** (persisted in EEPROM; with auto switch the rotation continues from it) | same as `5` |
| `7, n` | read effect parameters (no preview) | `7, n, fav, scale, speed` |
| `8, n, fav, scale, speed` | write effect parameters | same as `7` |

`proto` is `1` for firmware 1.3. A garland that does not answer `5` runs
stock firmware.

### Push

After `1, 1` the sender becomes the subscriber for 5 minutes (renewed by every
`1, 1`). Whenever settings or the shown effect change — UDP, button, off
timer, auto switch — the garland sends the `1, …` settings packet followed by
the `5, …` packet to the subscriber, at most every 200 ms.

### mDNS

Firmware 1.3 announces `_gyvertwink._udp` on port 8888 with TXT `proto=1`,
hostname `gyvertwink-XXXXXX` (ESP chip id). Home Assistant uses it for
zeroconf discovery.

## Effects

22 effects: indexes 0–10 are gradients, 11–21 Perlin noise, over the same 11
palettes: Party, Rainbow, Stripe, Sunset, Pepsi, Warm, Cold, Hot, Pink,
Cyber, RedWhite.

Speed: `128` stands still, higher moves forward, lower moves backward.
