// Garland tab: LED count, the calibration kept in HA, firmware info.

import { LED_MAX, esc, formatDate } from "../util.js";

export class GarlandTab {
  constructor(panel) {
    this.panel = panel;
  }

  get busy() {
    return false;
  }

  leave() {}

  render(content, g) {
    const t = this.panel.t;
    const stored = g.calibration;
    content.innerHTML = `
      <div class="card">
        <h2>${t.ledCount}</h2>
        <p class="muted">${t.ledCountHint}</p>
        <div class="row"><input type="number" id="leds" min="1" max="${LED_MAX}" value="${g.led_count}">
          <button id="ledsApply">${t.apply}</button></div>
      </div>
      <div class="card">
        <h2>${t.calibration}</h2>
        <p class="muted">${esc(stored
          ? t.storedMap(formatDate(stored.created, this.panel.language), stored.points.length)
          : t.noStoredMap)}</p>
        ${stored ? `<div class="row"><button class="secondary" id="restore">${t.restore}</button></div>` : ""}
      </div>
      <div class="card">
        <dl>
          <dt>${t.address}</dt><dd>${esc(g.host)}</dd>
          <dt>${t.firmware}</dt><dd>${g.extended ? t.firmwareExt : t.firmwareStock}</dd>
          ${g.mac ? `<dt>${t.mac}</dt><dd>${esc(g.mac)}</dd>` : ""}
        </dl>
      </div>`;
    const $ = (id) => this.panel.shadowRoot.getElementById(id);
    $("ledsApply").onclick = () => this._setLedCount(g, $("leds").value);
    if (stored) $("restore").onclick = (ev) => this._restore(g, ev.target);
  }

  async _setLedCount(g, value) {
    const t = this.panel.t;
    const count = Math.max(1, Math.min(LED_MAX, parseInt(value, 10) || 1));
    try {
      await this.panel.ws("led_count/set", { entry_id: g.entry_id, count });
      g.led_count = count;
      this.panel.toast(`${t.ledCount}: ${count}`);
    } catch (e) {
      this.panel.toast(t.error(e.message || e));
    }
  }

  async _restore(g, button) {
    const t = this.panel.t;
    button.disabled = true;
    try {
      await this.panel.ws("calibration/restore", { entry_id: g.entry_id });
      this.panel.toast(t.restored);
    } catch (e) {
      this.panel.toast(t.error(e.message || e));
    }
    button.disabled = false;
  }
}
