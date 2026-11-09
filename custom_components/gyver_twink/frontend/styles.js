// Panel styles, based on Home Assistant theme variables.

export const styles = `
:host { display: block; min-height: 100%; background: var(--primary-background-color);
  color: var(--primary-text-color); font-family: var(--ha-font-family-body, Roboto, sans-serif);
  -webkit-text-size-adjust: 100%; }
/* The panel handles safe areas itself (handle_safe_area): the header
   background runs under the iPhone status bar, like built-in panels. */
.toolbar { display: flex; align-items: center; box-sizing: border-box; gap: 4px;
  height: calc(var(--header-height, 56px) + env(safe-area-inset-top, 0px));
  padding: env(safe-area-inset-top, 0px) calc(4px + env(safe-area-inset-right, 0px)) 0
    calc(4px + env(safe-area-inset-left, 0px));
  background: var(--app-header-background-color, var(--primary-color));
  color: var(--app-header-text-color, white); font-size: 20px;
  border-bottom: var(--app-header-border-bottom, none); }
.toolbar .title { flex: 1; margin-left: 8px; }
.toolbar select { font: inherit; font-size: 14px; max-width: 45%; color: inherit;
  background: transparent; border: 1px solid currentColor; border-radius: 8px; padding: 4px 8px; }
.tabs { display: flex; gap: 4px; padding: 8px 16px 0; max-width: 760px; margin: 0 auto; box-sizing: border-box; }
.tabs button { flex: 1; background: none; color: var(--secondary-text-color); border-radius: 0;
  border-bottom: 2px solid transparent; padding: 10px 4px; }
.tabs button.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
.content { padding: 12px max(16px, env(safe-area-inset-right, 0px)) calc(32px + env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px)); max-width: 760px; margin: 0 auto; box-sizing: border-box; }
.card { background: var(--card-background-color); border-radius: var(--ha-card-border-radius, 12px);
  border: 1px solid var(--divider-color); padding: 16px; margin-bottom: 12px; }
h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
p { margin: 8px 0; line-height: 1.4; }
.muted { color: var(--secondary-text-color); font-size: 14px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
button { font: inherit; font-size: 15px; padding: 10px 16px; border-radius: 10px; border: none;
  cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, white); }
button.secondary { background: var(--secondary-background-color); color: var(--primary-text-color);
  border: 1px solid var(--divider-color); }
button.danger { background: var(--error-color, #db4437); }
button:disabled { opacity: .5; cursor: default; }
label.field { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; align-items: center;
  margin: 12px 0; font-size: 15px; }
label.field input[type=range] { grid-column: 1 / -1; width: 100%; accent-color: var(--primary-color); }
input[type=number] { font: inherit; width: 90px; padding: 8px; border-radius: 8px;
  border: 1px solid var(--divider-color); background: var(--card-background-color); color: inherit; }
.stage { position: relative; margin: 0 auto; background: #000; border-radius: 10px; overflow: hidden; }
.stage video, .stage canvas { display: block; width: 100%; height: 100%; }
.stage canvas { position: absolute; inset: 0; }
.bar { height: 6px; border-radius: 3px; background: var(--divider-color); overflow: hidden; margin: 8px 0; }
.bar > div { height: 100%; background: var(--primary-color); transition: width .2s; }
.warn { color: var(--warning-color, #ffa600); }
.bad { color: var(--error-color, #db4437); }
.ok { color: var(--success-color, #43a047); }
a { color: var(--primary-color); }
.eff { display: flex; align-items: center; gap: 8px; padding: 10px 0;
  border-bottom: 1px solid var(--divider-color); }
.eff:last-child { border-bottom: none; }
.eff .name { flex: 1; cursor: pointer; }
.eff .name small { display: block; color: var(--secondary-text-color); font-size: 12px; }
.icon-btn { background: none; color: var(--secondary-text-color); padding: 6px 10px; font-size: 20px; line-height: 1; }
.icon-btn.on { color: var(--warning-color, #ffa600); }
.eff-edit { padding: 0 0 8px; border-bottom: 1px solid var(--divider-color); }
dl { display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; margin: 0; font-size: 15px; }
dt { color: var(--secondary-text-color); }
dd { margin: 0; word-break: break-all; }
`;
