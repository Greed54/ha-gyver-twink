// node --test tests/frontend
import { test } from "node:test";
import assert from "node:assert/strict";
import { detect, fillMissing, findDoubtful, gridFor } from "../../custom_components/gyver_twink/frontend/vision.js";

const GX = 60, GY = 107;

// Seeded noise so the tests are reproducible.
function rng(seed) {
  return () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
}

function frame(rand, led, exposure = 0) {
  const map = new Float32Array(GX * GY);
  for (let i = 0; i < map.length; i++) map[i] = 20 + rand() * 4 + exposure;
  if (led) {
    for (let y = 0; y < GY; y++) {
      for (let x = 0; x < GX; x++) {
        const d = Math.hypot(x + 0.5 - led.x, y + 0.5 - led.y);
        map[y * GX + x] += Math.max(0, 120 - 60 * d);
      }
    }
  }
  return { map, gx: GX, gy: GY };
}

test("grid follows the frame aspect ratio", () => {
  assert.deepEqual(gridFor(720, 1280), { gx: 60, gy: 107 });
  assert.deepEqual(gridFor(1280, 720), { gx: 60, gy: 34 });
  assert.equal(gridFor(0, 0), null);
});

test("finds a lit LED with sub-cell accuracy despite an exposure shift", () => {
  const rand = rng(1);
  const base = frame(rand);
  let worst = 0;
  for (let k = 0; k < 100; k++) {
    const led = { x: 2 + rand() * 56, y: 2 + rand() * 103 };
    const hit = detect(frame(rand, led, 8), base, 20);
    assert.ok(hit, `LED at ${led.x},${led.y} not found`);
    worst = Math.max(worst, Math.hypot(hit.x + 0.5 - led.x, hit.y + 0.5 - led.y));
  }
  assert.ok(worst < 0.6, `worst error ${worst} cells`);
});

test("a brighter dark frame is not an LED", () => {
  const rand = rng(2);
  assert.equal(detect(frame(rand, null, 15), frame(rand), 20), null);
});

test("a point far from both neighbours is doubtful", () => {
  const pts = [[10, 10], [11, 12], [12, 14], [13, 16], [50, 90], [15, 20], [16, 22], [17, 24]]
    .map(([x, y]) => ({ x, y }));
  assert.deepEqual(findDoubtful(pts), [4]);
});

test("missing LEDs are interpolated or copied from the nearest one", () => {
  const p = (x, y) => ({ x, y });
  assert.deepEqual(fillMissing([null, p(10, 10), null, p(14, 20), null]), [
    [10, 10], [10, 10], [12, 15], [14, 20], [14, 20],
  ]);
  assert.throws(() => fillMissing([null, null]));
});
