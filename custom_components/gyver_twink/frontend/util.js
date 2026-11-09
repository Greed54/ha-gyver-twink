// Small helpers shared by the panel modules.

export const LED_MAX = 500; // firmware limit, protocol.LED_MAX

/** Escape text for use inside HTML. */
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export const formatDate = (iso, language) => (iso ? new Date(iso).toLocaleString(language) : "");
