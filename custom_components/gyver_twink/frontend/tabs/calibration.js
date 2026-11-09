// Calibration tab: the phone camera watches the tree while the garland lights
// its LEDs one by one; the brightest new spot is the LED position.
//
// Phases: idle → camera → prepare → run → review → saving → idle.
// A re-shoot of missed LEDs goes review → prepare → retake → review.

import { FrameSampler, averageFrames, detect, fillMissing, findDoubtful, gridFor, sleep } from "../vision.js";
import { esc, formatDate } from "../util.js";

const FRAMES = 3; // frames averaged per LED
const BASE_FRAMES = 6; // frames averaged for the dark reference
const CLEAR_DELAY = 1500; // ms for the strip to clear and the camera to settle
const UPLOAD_GAP = 0.06; // s per LED when writing the map (client packet gap)

export class CalibrationTab {
  constructor(panel) {
    this.panel = panel;
    this.sampler = new FrameSampler();
    this.state = { phase: "idle" };
    this.stream = null;
  }

  /** True while the camera or a calibration run must not be interrupted. */
  get busy() {
    return !["idle", "camera"].includes(this.state.phase);
  }

  leave() {
    this.stopCamera();
  }

  get t() {
    return this.panel.t;
  }

  $(id) {
    return this.panel.shadowRoot.getElementById(id);
  }

  render(content, g) {
    const t = this.t, s = this.state, prefs = this.panel.prefs;
    const busy = ["prepare", "run", "retake", "saving", "review"].includes(s.phase);
    content.innerHTML = `
      <div class="card">
        <p>${t.calibIntro}</p>
        ${this._secureHtml()}
        <p class="muted">${esc(this._storedText(g))}</p>
        <div id="status"></div>
        <div class="stage" id="stage" hidden><video playsinline muted autoplay></video><canvas></canvas></div>
        <div class="row" id="buttons"></div>
        <div ${busy ? "hidden" : ""}>
          <label class="field"><span>${t.settle}</span><span id="settleV">${prefs.settle} ${t.ms}</span>
            <input type="range" id="settle" min="150" max="1000" step="50" value="${prefs.settle}"></label>
          <label class="field"><span>${t.sensitivity}</span><span id="thrV">${prefs.threshold}</span>
            <input type="range" id="thr" min="5" max="80" step="1" value="${prefs.threshold}"></label>
        </div>
      </div>`;
    this.$("settle").oninput = (e) => {
      prefs.settle = +e.target.value;
      this.$("settleV").textContent = `${prefs.settle} ${t.ms}`;
      this.panel.savePrefs();
    };
    this.$("thr").oninput = (e) => {
      prefs.threshold = +e.target.value;
      this.$("thrV").textContent = prefs.threshold;
      this.panel.savePrefs();
    };
    if (this.stream) this._attachVideo();
    else if (g.calibration && s.phase === "idle") this._drawStored(g.calibration);
    this.renderControls();
  }

  _storedText(g) {
    const c = g.calibration;
    return c ? this.t.storedMap(formatDate(c.created, this.panel.language), c.points.length) : this.t.noStoredMap;
  }

  _secureHtml() {
    const t = this.t;
    if (window.isSecureContext && navigator.mediaDevices?.getUserMedia) return "";
    const ext = this.panel.hass.config?.external_url;
    const link = ext
      ? ` <a href="${esc(ext.replace(/\/$/, "") + location.pathname)}" target="_blank">${t.openHttps}</a>`
      : ` ${t.openExternal}`;
    return `<p class="bad">${esc(t.httpsOnly(location.origin))}${link}</p>`;
  }

  renderControls() {
    const t = this.t, s = this.state;
    const buttons = this.$("buttons"), status = this.$("status");
    if (!buttons) return;
    buttons.innerHTML = "";
    status.innerHTML = "";
    const button = (label, fn, cls = "") => {
      const el = document.createElement("button");
      el.textContent = label;
      if (cls) el.className = cls;
      el.onclick = fn;
      buttons.append(el);
      return el;
    };
    switch (s.phase) {
      case "idle":
        button(t.cameraOn, () => this.startCamera()).disabled =
          !(window.isSecureContext && navigator.mediaDevices?.getUserMedia);
        break;
      case "camera":
        button(t.start, () => this.run());
        button(t.cameraOff, () => this.stopCamera(), "secondary");
        break;
      case "prepare":
        status.innerHTML = `<p>${t.preparing}</p>`;
        button(t.cancel, () => this.cancel(), "secondary");
        break;
      case "run":
      case "retake": {
        const total = s.queue.length, done = s.pos;
        const left = Math.max(0, total - done) * (this.panel.prefs.settle + 150);
        const eta = left > 60000 ? `${Math.ceil(left / 60000)} ${t.min}` : `${Math.ceil(left / 1000)} ${t.sec}`;
        status.innerHTML = `<p>${t.progress(Math.min(done + 1, total), total, eta)}</p>
          <div class="bar"><div style="width:${(100 * done) / total}%"></div></div>`;
        button(s.paused ? t.resume : t.pause, () => {
          s.paused = !s.paused;
          this.renderControls();
        }, "secondary");
        button(t.cancel, () => this.cancel(), "secondary");
        break;
      }
      case "review": {
        const missed = s.points.flatMap((p, i) => (p ? [] : [i]));
        const doubtful = findDoubtful(s.points);
        s.redo = [...missed, ...doubtful].sort((a, b) => a - b);
        const found = s.points.length - missed.length;
        status.innerHTML = `<p>${t.review(found, s.points.length)}</p>
          <p class="${s.redo.length ? "warn" : "ok"}">${
            s.redo.length ? t.missedInfo(missed.length, doubtful.length) : t.allFound}</p>`;
        button(t.save, () => this.save()).disabled = found === 0;
        if (s.redo.length && this.stream) button(t.retake(s.redo.length), () => this.run(s.redo), "secondary");
        button(t.cancel, () => this.cancel(), "secondary");
        break;
      }
      case "saving":
        status.innerHTML = `<p>${s.message || ""}</p><div class="bar"><div style="width:100%"></div></div>`;
        break;
    }
  }

  // ---------------------------------------------------------------- camera

  async startCamera() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
    } catch (e) {
      this.panel.toast(this.t.error(`${e.name}: ${e.message}`));
      return;
    }
    this.state = { phase: "camera" };
    this._attachVideo();
    this.renderControls();
    const draw = () => {
      if (!this.stream) return;
      requestAnimationFrame(draw);
      this._drawOverlay();
    };
    draw();
  }

  stopCamera() {
    this.stream?.getTracks().forEach((tr) => tr.stop());
    this.stream = null;
    this.video = null;
    this._releaseWakeLock();
    if (!this.busy) {
      this.state = { phase: "idle" };
      this.panel.renderTab(this);
    }
  }

  _attachVideo() {
    const stage = this.$("stage");
    if (!stage) return;
    const video = stage.querySelector("video");
    stage.hidden = false;
    if (video.srcObject !== this.stream) video.srcObject = this.stream;
    video.play().catch(() => {});
    const fit = () => {
      const vw = video.videoWidth || 9, vh = video.videoHeight || 16;
      const w = Math.min(stage.parentElement.clientWidth, (window.innerHeight * 0.62 * vw) / vh);
      stage.style.width = `${w}px`;
      stage.style.height = `${(w * vh) / vw}px`;
    };
    video.onloadedmetadata = fit;
    fit();
    this.video = video;
    this.overlay = stage.querySelector("canvas");
  }

  /** Points found so far, the last measurement and (in review) LEDs to re-shoot. */
  _drawOverlay() {
    const cv = this.overlay, video = this.video, s = this.state;
    if (!cv || !video || !video.videoWidth) return;
    const w = cv.clientWidth, h = cv.clientHeight;
    if (cv.width !== w * 2) {
      cv.width = w * 2;
      cv.height = h * 2;
    }
    const ctx = cv.getContext("2d");
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const g = gridFor(video.videoWidth, video.videoHeight);
    const sx = w / g.gx, sy = h / g.gy;
    const pts = s.points || [];
    pts.forEach((p, i) => {
      if (!p) return;
      ctx.fillStyle = `hsl(${(i * 300) / Math.max(1, pts.length)}, 90%, 55%)`;
      ctx.beginPath();
      ctx.arc((p.x + 0.5) * sx, (p.y + 0.5) * sy, 3, 0, 7);
      ctx.fill();
    });
    if (s.last) {
      ctx.strokeStyle = "#00e676";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc((s.last.x + 0.5) * sx, (s.last.y + 0.5) * sy, 14, 0, 7);
      ctx.stroke();
    }
    if (s.phase === "review" && s.redo?.length && pts.some(Boolean)) {
      const filled = fillMissing(pts);
      ctx.strokeStyle = "#ff1744";
      ctx.lineWidth = 2;
      s.redo.forEach((i) => {
        const [x, y] = filled[i];
        ctx.beginPath();
        ctx.arc((x + 0.5) * sx, (y + 0.5) * sy, 7, 0, 7);
        ctx.stroke();
      });
    }
  }

  /** The map saved in HA, drawn without the camera. */
  _drawStored(stored) {
    const stage = this.$("stage");
    const [gx, gy] = stored.grid;
    const w = Math.min(stage.parentElement.clientWidth, (window.innerHeight * 0.5 * gx) / gy);
    const h = (w * gy) / gx;
    stage.hidden = false;
    stage.style.width = `${w}px`;
    stage.style.height = `${h}px`;
    stage.querySelector("video").hidden = true;
    const cv = stage.querySelector("canvas");
    cv.width = w * 2;
    cv.height = h * 2;
    const ctx = cv.getContext("2d");
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    const missed = new Set(stored.missed || []);
    stored.points.forEach(([x, y], i) => {
      ctx.fillStyle = missed.has(i) ? "#ff1744" : `hsl(${(i * 300) / stored.points.length}, 90%, 55%)`;
      ctx.beginPath();
      ctx.arc(((x + 0.5) * w) / gx, ((y + 0.5) * h) / gy, 3, 0, 7);
      ctx.fill();
    });
  }

  async _wakeLock() {
    try {
      this.lock = await navigator.wakeLock?.request("screen");
    } catch (e) {
      /* not supported: the user keeps the screen on */
    }
  }

  _releaseWakeLock() {
    this.lock?.release().catch(() => {});
    this.lock = null;
  }

  // ---------------------------------------------------------------- run

  /** Scan all LEDs, or only `indices` (re-shoot after review). */
  async run(indices) {
    const g = this.panel.garland;
    const entry_id = g.entry_id;
    const prefs = this.panel.prefs;
    const points = indices ? this.state.points : new Array(g.led_count).fill(null);
    const s = (this.state = {
      phase: "prepare",
      points,
      grid: this.state.grid,
      queue: indices || [...points.keys()],
      pos: 0,
      paused: false,
      aborted: false,
    });
    this.renderControls();
    await this._wakeLock();
    try {
      await this.panel.ws("calibration/start", { entry_id });
      await sleep(CLEAR_DELAY);
      if (s.aborted) return;
      const base = await averageFrames(this.video, this.sampler, BASE_FRAMES);
      if (!base) throw new Error("no camera frames");
      s.grid = [base.gx, base.gy];
      s.phase = indices ? "retake" : "run";
      this.renderControls();
      for (; s.pos < s.queue.length; s.pos++) {
        while (s.paused && !s.aborted) await sleep(200);
        if (s.aborted) return;
        const i = s.queue[s.pos];
        // The firmware stores the previous LED while lighting this one.
        const prev = (i > 0 && points[i - 1]) || { x: 0, y: 0 };
        await this.panel.ws("calibration/led", { entry_id, index: i, x: Math.round(prev.x), y: Math.round(prev.y) });
        await sleep(prefs.settle);
        const cur = await averageFrames(this.video, this.sampler, FRAMES);
        const hit = cur && detect(cur, base, prefs.threshold);
        if (hit || !indices) points[i] = hit;
        s.last = hit;
        this.renderControls();
      }
      s.last = null;
      s.phase = "review";
      this.renderControls();
    } catch (e) {
      if (s.aborted) return;
      this.panel.toast(this.t.error(e.message || e));
      this.state = { phase: this.stream ? "camera" : "idle" };
      this.renderControls();
    } finally {
      this._releaseWakeLock();
    }
  }

  async save() {
    const g = this.panel.garland;
    const s = this.state;
    const missed = s.points.flatMap((p, i) => (p ? [] : [i]));
    const points = fillMissing(s.points);
    s.phase = "saving";
    s.message = this.t.saving(points.length, Math.ceil(points.length * UPLOAD_GAP + 1));
    this.renderControls();
    try {
      g.calibration = await this.panel.ws("calibration/save", { entry_id: g.entry_id, points, grid: s.grid, missed });
      this.panel.toast(this.t.saved);
      this.state = { phase: "idle" };
      this.stopCamera();
    } catch (e) {
      this.panel.toast(this.t.error(e.message || e));
      s.phase = "review";
      this.renderControls();
    }
  }

  async cancel() {
    const g = this.panel.garland;
    if (!g.calibration && !confirm(this.t.cancelWarn)) return;
    this.state.aborted = true;
    this.state = { phase: "saving", message: "…" };
    this.renderControls();
    try {
      const res = await this.panel.ws("calibration/cancel", { entry_id: g.entry_id });
      this.panel.toast(this.t.cancelled(res.restored));
    } catch (e) {
      this.panel.toast(this.t.error(e.message || e));
    }
    this.state = { phase: this.stream ? "camera" : "idle" };
    this.renderControls();
  }
}
