// Effects tab: favourite, speed and scale of all 22 effects at once.
// Firmware 1.3 reports them directly; stock firmware only while an effect
// is shown (30 s preview), so there the parameters appear one by one.

import { esc } from "../util.js";

export class EffectsTab {
  constructor(panel) {
    this.panel = panel;
    this.entry = null; // garland the parameters belong to
    this.params = [];
    this.open = null; // index of the effect being edited
  }

  get busy() {
    return false;
  }

  leave() {}

  get t() {
    return this.panel.t;
  }

  async render(content, g) {
    if (this.entry !== g.entry_id) {
      this.entry = g.entry_id;
      this.params = new Array(this.panel.effectKeys.length).fill(null);
      this.open = null;
      content.innerHTML = `<div class="card"><p class="muted">…</p></div>`;
      if (g.extended) {
        try {
          this.params = (await this.panel.ws("effects/get", { entry_id: g.entry_id })).params;
        } catch (e) {
          this.panel.toast(this.t.error(e.message || e));
        }
      }
      if (this.panel.tab !== this) return;
    }
    this._renderList(content, g);
  }

  _renderList(content, g) {
    const t = this.t;
    content.innerHTML = `<div class="card">
        ${g.extended ? "" : `<p class="muted">${t.effectsStock}</p>`}
        <div id="effList"></div></div>`;
    const list = this.panel.shadowRoot.getElementById("effList");
    this.panel.effectKeys.forEach((key, i) => {
      const p = this.params[i];
      const row = document.createElement("div");
      row.className = "eff";
      row.innerHTML = `
        <span class="name">${esc(this.panel.effectName(key))}<small>${p ? this._summary(p) : ""}</small></span>
        <button class="icon-btn ${p?.favorite ? "on" : ""}" title="${t.favorite}" ${p ? "" : "disabled"}>${
          p?.favorite ? "★" : "☆"}</button>
        <button class="icon-btn" title="${t.show}">▶</button>`;
      const [favBtn, showBtn] = row.querySelectorAll("button");
      row.querySelector(".name").onclick = () => {
        if (!p) return this._preview(g, i, true);
        this.open = this.open === i ? null : i;
        this._renderList(content, g);
      };
      favBtn.onclick = () => this._toggleFavorite(content, g, i);
      showBtn.onclick = () => this._preview(g, i, !g.extended);
      list.append(row);
      if (this.open === i && p) list.append(this._editor(g, i, p));
    });
  }

  _summary(p) {
    return `${this.t.speed} ${p.speed} · ${this.t.scale} ${p.scale}`;
  }

  _editor(g, i, p) {
    const t = this.t;
    const box = document.createElement("div");
    box.className = "eff-edit";
    box.innerHTML = ["speed", "scale"]
      .map((f) => `<label class="field"><span>${t[f]}</span><span data-v="${f}">${p[f]}</span>
          <input type="range" min="0" max="255" value="${p[f]}" data-f="${f}"></label>`)
      .join("");
    box.querySelectorAll("input").forEach((inp) => {
      const f = inp.dataset.f;
      inp.oninput = () => (box.querySelector(`[data-v=${f}]`).textContent = inp.value);
      inp.onchange = async () => {
        await this._set(g, i, { [f]: +inp.value });
        const small = box.previousElementSibling?.querySelector("small");
        if (small && this.params[i]) small.textContent = this._summary(this.params[i]);
      };
    });
    return box;
  }

  async _toggleFavorite(content, g, i) {
    const p = this.params[i];
    // Stock firmware hangs with no favourites; 1.3 copes, but it makes no sense.
    if (p.favorite && g.extended && this.params.filter((x) => x?.favorite).length <= 1) {
      this.panel.toast(this.t.lastFavorite);
      return;
    }
    await this._set(g, i, { favorite: !p.favorite });
    this._renderList(content, g);
  }

  async _preview(g, i, open) {
    try {
      this.params[i] = await this.panel.ws("effects/preview", { entry_id: g.entry_id, index: i });
      if (open) this.open = i;
      this.panel.renderTab(this);
    } catch (e) {
      this.panel.toast(this.t.error(e.message || e));
    }
  }

  async _set(g, i, changes) {
    const next = { ...this.params[i], ...changes };
    try {
      this.params[i] = await this.panel.ws("effects/set", {
        entry_id: g.entry_id,
        index: i,
        favorite: next.favorite,
        scale: next.scale,
        speed: next.speed,
      });
    } catch (e) {
      this.panel.toast(this.t.error(e.message || e));
    }
  }
}
