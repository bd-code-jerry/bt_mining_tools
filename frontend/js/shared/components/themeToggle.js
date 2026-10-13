import { THEME_PRESETS } from "../../theme.js";
import { escapeHtml } from "../utils/format.js";

// Keep the shared export name so all auth states use the same appearance selector.
export function themeToggleHtml(variant = "") {
  const variantClass = variant ? ` ${escapeHtml(variant)}` : "";
  const current = globalThis.document?.documentElement?.dataset.theme || "light";
  const options = THEME_PRESETS.map((preset) => `<option value="${preset.id}"${preset.id === current ? " selected" : ""}>${preset.label}</option>`).join("");
  return `
    <label class="theme-control${variantClass}">
      <span>Appearance</span>
      <select class="theme-select" data-theme-select>${options}</select>
    </label>
  `;
}
