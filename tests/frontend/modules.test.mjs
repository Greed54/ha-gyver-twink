// Every panel module loads and the custom element gets defined.
import { test } from "node:test";
import assert from "node:assert/strict";

test("panel modules import cleanly", async () => {
  const defined = {};
  globalThis.HTMLElement = class {};
  globalThis.customElements = { define: (name, cls) => (defined[name] = cls) };
  await import("../../custom_components/gyver_twink/frontend/gyver-twink-panel.js");
  assert.equal(typeof defined["gyver-twink-panel"], "function");
});

test("both languages have the same texts", async () => {
  const { texts } = await import("../../custom_components/gyver_twink/frontend/i18n.js");
  const en = texts("en"), ru = texts("ru");
  assert.deepEqual(Object.keys(ru).sort(), Object.keys(en).sort());
  assert.equal(texts("de-DE"), en);
  assert.equal(texts("ru-UA"), ru);
});
