#!/usr/bin/env python3
"""GyverTwink firmware emulator (UDP 8888) for testing without a garland.

Mirrors firmware logic from firmware/GyverTwink_v1.3/parsing.ino:
  --stock   behave like stock 1.2 (no extended commands, drops ANY packet
            that comes within 50 ms of the previous one, hangs when no
            effect is a favourite)
  default   behave like 1.3 (extended commands, push to subscriber)

Usage: python3 tools/emulator.py [--stock] [--port 8888] [--mac aa:bb:..]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time

EFF_AMOUNT = 22
PROTO_VER = 1
LED_MAX = 500

log = logging.getLogger("emulator")


class Timer:
    def __init__(self, prd: float, state: bool = True) -> None:
        self.prd = prd
        self.state = state
        self.t = time.monotonic()

    def restart(self) -> None:
        self.t = time.monotonic()
        self.state = True

    def stop(self) -> None:
        self.state = False

    def ready(self) -> bool:
        if self.state and time.monotonic() - self.t >= self.prd:
            self.restart()
            return True
        return False


class Garland(asyncio.DatagramProtocol):
    def __init__(self, stock: bool, mac: bytes, ip_last: int) -> None:
        self.stock = stock
        self.mac = mac
        self.ip_last = ip_last
        self.led_am = 150
        self.power = True
        self.bright = 235
        self.auto = True
        self.rnd = False
        self.prd = 1
        self.turn_off = False
        self.off_tmr = 60
        self.effs = [[1, 50, 150] for _ in range(EFF_AMOUNT)]  # fav, scale, speed
        self.cur = 0
        self.force_eff = 0
        self.force_tmr = Timer(30, False)
        self.switch_tmr = Timer(self.prd * 60, self.auto)
        self.off_timer = Timer(self.off_tmr * 60, False)
        self.hung = False
        self.last_rx = 0.0
        self.last_cmd: tuple[int, int] | None = None
        self.sub: tuple[str, int] | None = None
        self.sub_t = 0.0
        self.last_hash: bytes | None = None
        self.transport: asyncio.DatagramTransport | None = None

    # ---------- helpers ----------
    def shown(self) -> int:
        return self.force_eff if self.force_tmr.state else self.cur

    def settings(self) -> bytes:
        return bytes([1, self.led_am // 100, self.led_am % 100, self.power, self.bright,
                      self.auto, self.rnd, self.prd, self.turn_off, self.off_tmr])

    def ext(self) -> bytes:
        return bytes([5, PROTO_VER, self.shown(), EFF_AMOUNT]) + self.mac

    def send(self, data: bytes, addr) -> None:
        assert self.transport
        log.debug("-> %s %s", addr, data.hex(" "))
        self.transport.sendto(b"GT" + data, addr)

    def switch_eff(self) -> None:
        if not any(e[0] for e in self.effs):
            if self.stock:
                log.warning("no favourites: stock firmware hangs forever")
                self.hung = True
                return
            self.cur = (self.cur + 1) % EFF_AMOUNT
            return
        while True:
            self.cur = random.randrange(EFF_AMOUNT) if self.rnd else (self.cur + 1) % EFF_AMOUNT
            if self.effs[self.cur][0]:
                break
        log.info("effect -> %d", self.cur)

    # ---------- loop (timers, push) ----------
    async def run(self) -> None:
        while True:
            await asyncio.sleep(0.05)
            if self.hung:
                continue
            if self.force_tmr.ready():
                self.force_tmr.stop()
                self.switch_eff()
            if not self.force_tmr.state and self.switch_tmr.ready():
                self.switch_eff()
            if self.off_timer.ready():
                self.off_timer.stop()
                self.turn_off = False
                self.power = False
                log.info("off timer fired")
            self.notify()

    def notify(self) -> None:
        if self.stock or not self.sub:
            return
        if time.monotonic() - self.sub_t > 300:
            self.sub = None
            return
        h = self.settings() + bytes([self.shown()])
        if h == self.last_hash:
            return
        self.last_hash = h
        self.send(self.settings(), self.sub)
        self.send(self.ext(), self.sub)

    # ---------- parsing ----------
    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if self.hung:
            return
        log.debug("<- %s %s", addr, data.hex(" "))
        if len(data) < 3 or data[:2] != b"GT":
            return
        u = list(data[2:]) + [0] * 8
        now = time.monotonic()
        key = (u[0], u[1])
        if now - self.last_rx < 0.05 and (self.stock or key == self.last_cmd):
            log.warning("dropped by anti-bounce: %s", data[2:].hex(" "))
            return
        self.last_rx = now
        self.last_cmd = key
        cmd = u[0]

        if cmd == 0:
            self.send(bytes([0, self.ip_last]), addr)
        elif cmd == 1:
            if not self.stock and len(data) > 3 and u[1] == 1:
                self.sub, self.sub_t = addr, now
            self.send(self.settings(), addr)
        elif cmd == 2:
            self.force_tmr.stop()
            sub, v = u[1], u[2]
            if sub == 0:
                self.led_am = max(1, min(LED_MAX, u[2] * 100 + u[3]))
            elif sub == 1:
                self.power = bool(v)
            elif sub == 2:
                self.bright = v
            elif sub == 3:
                self.auto = bool(v)
                self.switch_tmr.restart() if self.auto else self.switch_tmr.stop()
            elif sub == 4:
                self.rnd = bool(v)
            elif sub == 5:
                self.prd = max(1, v)
                self.switch_tmr.prd = self.prd * 60
                if self.auto:
                    self.switch_tmr.restart()
            elif sub == 6:
                self.switch_eff()
                if self.auto:
                    self.switch_tmr.restart()
            elif sub == 7:
                self.turn_off = bool(v)
                self.off_timer.restart() if self.turn_off else self.off_timer.stop()
            elif sub == 8:
                self.off_tmr = max(1, v)
                self.off_timer.prd = self.off_tmr * 60
                if self.turn_off:
                    self.off_timer.restart()
        elif cmd == 4:
            if u[1] == 0 and u[2] >= EFF_AMOUNT:
                return
            self.force_tmr.restart()
            if u[1] == 0:
                self.force_eff = u[2]
                e = self.effs[self.force_eff]
                self.send(bytes([4, e[0], e[1], e[2]]), addr)
            elif u[1] in (1, 2, 3):
                self.effs[self.force_eff][u[1] - 1] = u[2]
        elif self.stock:
            return  # stock firmware ignores unknown commands
        elif cmd == 5:
            self.send(self.ext(), addr)
        elif cmd == 6:
            if u[1] >= EFF_AMOUNT:
                return
            self.force_tmr.stop()
            self.cur = u[1]
            if self.auto:
                self.switch_tmr.restart()
            self.send(self.ext(), addr)
        elif cmd in (7, 8):
            n = u[1]
            if n >= EFF_AMOUNT:
                return
            if cmd == 8:
                if len(data) < 7:
                    return
                self.effs[n] = [u[2], u[3], u[4]]
            e = self.effs[n]
            self.send(bytes([7, n, e[0], e[1], e[2]]), addr)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", action="store_true")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--mac", default="de:ad:be:ef:00:01")
    ap.add_argument("--ip-last", type=int, default=214)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    g = Garland(a.stock, bytes.fromhex(a.mac.replace(":", "")), a.ip_last)
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(lambda: g, local_addr=(a.bind, a.port))
    log.info("GyverTwink emulator (%s) on %s:%d", "stock" if a.stock else "1.3", a.bind, a.port)
    await g.run()


if __name__ == "__main__":
    asyncio.run(main())
