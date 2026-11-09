// GyverTwink setup panel for Home Assistant: camera calibration, effect
// editor and LED count. Everyday control stays in the integration entities.
//
// Plain ES modules, no build step. The panel talks to the integration over
// the Home Assistant websocket (gyver_twink/* commands, websocket_api.py).
//
//   gyver-twink-panel.js  shell: toolbar, garland picker, tabs
//   tabs/*.js             one class per tab: render(content, garland), leave(), busy
//   vision.js             image processing for calibration (tested in node)
//   i18n.js, styles.js, util.js

import { texts } from "./i18n.js";
import { styles } from "./styles.js";
import { esc } from "./util.js";
import { CalibrationTab } from "./tabs/calibration.js";
import { EffectsTab } from "./tabs/effects.js";
import { GarlandTab } from "./tabs/garland.js";

const STORE_KEY = "gyver-twink-panel";
const OFFLINE_POLL = 10000; // ms between checks for a garland coming online

class GyverTwinkPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.prefs = { settle: 300, threshold: 20, tab: "calib", ...this._loadPrefs() };
    this.garlands = null;
    this.effectKeys = [];
    this.tabs = {
      calib: new CalibrationTab(this),
      effects: new EffectsTab(this),
      garland: new GarlandTab(this),
    };
  }

  // ---------------------------------------------------------------- HA API

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first) this._init();
  }

  get hass() {
    return this._hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    if (this._hass) this._startPolling();
  }

  disconnectedCallback() {
    clearInterval(this._poll);
    this._poll = null;
    this.tab?.leave();
  }

  // ---------------------------------------------------------------- shared by tabs

  get language() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  get t() {
    return texts(this.language);
  }

  get tab() {
    return this.tabs[this.prefs.tab] || this.tabs.calib;
  }

  get garland() {
    return this.garlands?.find((g) => g.entry_id === this.prefs.entry);
  }

  ws(command, data = {}) {
    return this._hass.callWS({ type: `gyver_twink/${command}`, ...data });
  }

  toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }

  effectName(key) {
    return this._hass.localize?.(`component.gyver_twink.entity.light.garland.state_attributes.effect.state.${key}`) || key;
  }

  savePrefs() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(this.prefs));
    } catch (e) {
      /* private mode: preferences live until reload */
    }
  }

  /** Re-render a tab if it is the one shown. */
  renderTab(tab = this.tab) {
    if (tab !== this.tab) return;
    const content = this.shadowRoot.getElementById("content");
    if (!content || this.garlands === null) return;
    const g = this.garland, t = this.t;
    if (!g) content.innerHTML = `<div class="card"><p>${t.noGarlands}</p></div>`;
    else if (!g.connected) content.innerHTML = `<div class="card"><p>${esc(t.offline(g.title, g.host))}</p></div>`;
    else tab.render(content, g);
  }

  // ---------------------------------------------------------------- internals

  _loadPrefs() {
    try {
      return JSON.parse(localStorage.getItem(STORE_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  async _init() {
    this._renderShell();
    try {
      await this._hass.loadBackendTranslation?.("entity", "gyver_twink");
    } catch (e) {
      /* effect names fall back to keys */
    }
    await this._loadGarlands();
    this._startPolling();
  }

  _startPolling() {
    if (this._poll) return;
    this._poll = setInterval(() => {
      if (!this.tab.busy && !this.garland?.connected) this._loadGarlands();
    }, OFFLINE_POLL);
  }

  async _loadGarlands() {
    try {
      const res = await this.ws("garlands");
      this.garlands = res.garlands;
      this.effectKeys = res.effects;
    } catch (e) {
      this.garlands = [];
      this.toast(this.t.error(e.message || e));
    }
    if (!this.garland) this.prefs.entry = this.garlands[0]?.entry_id;
    this._renderNav();
    this.renderTab();
  }

  _renderShell() {
    this.shadowRoot.innerHTML = `
      <style>${styles}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button><span class="title">GyverTwink</span>
        <select id="garland" hidden></select>
      </div>
      <div class="tabs" id="tabs"></div>
      <div class="content" id="content"></div>`;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    menu.hass = this._hass;
    menu.narrow = this._narrow;
    this.shadowRoot.getElementById("garland").onchange = (e) => this._switch({ entry: e.target.value });
  }

  _renderNav() {
    const t = this.t;
    const select = this.shadowRoot.getElementById("garland");
    const list = this.garlands || [];
    select.hidden = list.length < 2;
    select.innerHTML = list
      .map((g) => `<option value="${esc(g.entry_id)}" ${g.entry_id === this.prefs.entry ? "selected" : ""}>${esc(g.title)}</option>`)
      .join("");
    const tabs = this.shadowRoot.getElementById("tabs");
    tabs.innerHTML = Object.entries(t.tabs)
      .map(([key, label]) => `<button data-tab="${key}" class="${this.prefs.tab === key ? "active" : ""}">${label}</button>`)
      .join("");
    tabs.querySelectorAll("button").forEach((b) => (b.onclick = () => this._switch({ tab: b.dataset.tab })));
  }

  /** Change tab and/or garland; not while a calibration is running. */
  _switch({ tab, entry }) {
    if (this.tab.busy) {
      this._renderNav();
      return;
    }
    this.tab.leave();
    if (tab) this.prefs.tab = tab;
    if (entry) this.prefs.entry = entry;
    this.savePrefs();
    this._renderNav();
    this.renderTab();
  }
}

customElements.define("gyver-twink-panel", GyverTwinkPanel);
