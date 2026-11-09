// Image processing for camera calibration. Pure functions plus a small
// frame sampler; no Home Assistant or panel state, so it can be tested in node.

export const GRID_X = 60; // calibration grid width, same as the GyverTwink app
const SUB = 4; // samples per grid cell side (block average)

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Grid size for a video frame: GRID_X columns, rows by aspect ratio. */
export function gridFor(width, height) {
  if (!width || !height) return null;
  return { gx: GRID_X, gy: Math.min(255, Math.max(1, Math.round((GRID_X * height) / width))) };
}

/** Brightness map of a video frame: one value per grid cell, block averaged. */
export class FrameSampler {
  constructor() {
    this.canvas = document.createElement("canvas");
    this.ctx = null;
  }

  sample(video) {
    const g = gridFor(video.videoWidth, video.videoHeight);
    if (!g) return null;
    const w = g.gx * SUB, h = g.gy * SUB;
    if (this.canvas.width !== w || this.canvas.height !== h || !this.ctx) {
      this.canvas.width = w;
      this.canvas.height = h;
      this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });
    }
    this.ctx.drawImage(video, 0, 0, w, h);
    const px = this.ctx.getImageData(0, 0, w, h).data;
    const map = new Float32Array(g.gx * g.gy);
    for (let y = 0; y < h; y++) {
      const row = ((y / SUB) | 0) * g.gx;
      for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4;
        map[row + ((x / SUB) | 0)] += px[i] + px[i + 1] + px[i + 2];
      }
    }
    const k = 3 * SUB * SUB;
    for (let i = 0; i < map.length; i++) map[i] /= k;
    return { map, ...g };
  }
}

/** Wait for the next decoded video frame. */
function nextFrame(video) {
  if (video.requestVideoFrameCallback) {
    return new Promise((r) => video.requestVideoFrameCallback(() => r()));
  }
  return sleep(34);
}

/** Average brightness map over n consecutive frames (less sensor noise). */
export async function averageFrames(video, sampler, n) {
  let acc = null, g = null;
  for (let i = 0; i < n; i++) {
    await nextFrame(video);
    const s = sampler.sample(video);
    if (!s) continue;
    g = s;
    if (!acc || acc.length !== s.map.length) acc = new Float32Array(s.map.length);
    for (let j = 0; j < acc.length; j++) acc[j] += s.map[j] / n;
  }
  return g ? { map: acc, gx: g.gx, gy: g.gy } : null;
}

/**
 * Find the lit LED: brightness gain over the dark frame, corrected for a
 * global exposure shift (median gain), then the weighted centre of the
 * brightest spot. Returns {x, y, peak} in grid cells, or null if nothing
 * rose above the threshold.
 */
export function detect(cur, base, threshold) {
  const { gx, gy } = cur;
  const n = cur.map.length;
  const d = new Float32Array(n);
  for (let i = 0; i < n; i++) d[i] = cur.map[i] - base.map[i];
  const sample = [];
  for (let i = 0; i < n; i += 7) sample.push(d[i]);
  sample.sort((a, b) => a - b);
  const offset = sample[sample.length >> 1] || 0;
  let max = -Infinity, maxi = 0;
  for (let i = 0; i < n; i++) {
    d[i] -= offset;
    if (d[i] > max) {
      max = d[i];
      maxi = i;
    }
  }
  if (max < threshold) return null;
  const mx = maxi % gx, my = (maxi / gx) | 0;
  let sx = 0, sy = 0, sw = 0;
  for (let y = Math.max(0, my - 2); y <= Math.min(gy - 1, my + 2); y++) {
    for (let x = Math.max(0, mx - 2); x <= Math.min(gx - 1, mx + 2); x++) {
      const v = d[y * gx + x] - max / 2;
      if (v > 0) {
        sx += v * x;
        sy += v * y;
        sw += v;
      }
    }
  }
  return { x: sw ? sx / sw : mx, y: sw ? sy / sw : my, peak: max };
}

/** Indices of LEDs far from both neighbours while those are close: probably a reflection. */
export function findDoubtful(points) {
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const steps = [];
  for (let i = 1; i < points.length; i++) {
    if (points[i] && points[i - 1]) steps.push(dist(points[i], points[i - 1]));
  }
  if (steps.length < 5) return [];
  steps.sort((a, b) => a - b);
  const limit = 4 * steps[steps.length >> 1] + 3;
  const out = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (!p) continue;
    const a = points[i - 1], b = points[i + 1];
    if (a && b && dist(p, a) > limit && dist(p, b) > limit && dist(a, b) < limit) out.push(i);
  }
  return out;
}

/** Integer [x, y] for every LED; LEDs not seen are filled in from their nearest found neighbours. */
export function fillMissing(points) {
  if (!points.some(Boolean)) throw new Error("no LEDs were found");
  const out = [];
  for (let i = 0; i < points.length; i++) {
    if (points[i]) {
      out.push(points[i]);
      continue;
    }
    let a = i - 1;
    while (a >= 0 && !points[a]) a--;
    let b = i + 1;
    while (b < points.length && !points[b]) b++;
    const pa = a >= 0 ? points[a] : null, pb = b < points.length ? points[b] : null;
    if (pa && pb) {
      const t = (i - a) / (b - a);
      out.push({ x: pa.x + (pb.x - pa.x) * t, y: pa.y + (pb.y - pa.y) * t });
    } else out.push(pa || pb);
  }
  return out.map((p) => [Math.round(p.x), Math.round(p.y)]);
}
