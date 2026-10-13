export const THEME_STORAGE_KEY = "bd-dashboard-theme";
export const THEME_PRESETS = Object.freeze([
  { id: "light", label: "Light", colorScheme: "light" },
  { id: "dark", label: "Dark", colorScheme: "dark" },
  { id: "sand", label: "Sand", colorScheme: "light" },
  { id: "forest", label: "Forest", colorScheme: "dark" },
  { id: "midnight", label: "Midnight", colorScheme: "dark" },
]);

function getStorage() {
  try { return globalThis.localStorage; } catch (_) { return null; }
}

function presetFor(theme) {
  return THEME_PRESETS.find((preset) => preset.id === theme) || THEME_PRESETS[0];
}

function applyTheme(root, theme) {
  const preset = presetFor(theme);
  root.dataset.theme = preset.id;
  if (root.style) root.style.colorScheme = preset.colorScheme;
  return preset.id;
}

export function initializeTheme({ root = globalThis.document?.documentElement, storage = getStorage() } = {}) {
  if (!root) throw new Error("A document root is required to initialize the theme.");
  let saved;
  try { saved = storage?.getItem(THEME_STORAGE_KEY); } catch (_) { /* Use Light when storage is blocked. */ }
  return applyTheme(root, saved);
}

export function selectTheme(theme, { root = globalThis.document?.documentElement, storage = getStorage() } = {}) {
  if (!root) throw new Error("A document root is required to select the theme.");
  const selected = applyTheme(root, theme);
  try { storage?.setItem(THEME_STORAGE_KEY, selected); } catch (_) { /* Switching still works without persistence. */ }
  return selected;
}

// Preserve the old helper for integrations that still use a quick Light/Dark toggle.
export function toggleTheme({ root = globalThis.document?.documentElement, storage = getStorage() } = {}) {
  if (!root) throw new Error("A document root is required to toggle the theme.");
  const theme = presetFor(root.dataset.theme).colorScheme === "dark" ? "light" : "dark";
  return selectTheme(theme, { root, storage });
}

export function syncThemeButtons(scope = globalThis.document, root = globalThis.document?.documentElement) {
  if (!scope?.querySelectorAll) return;
  const preset = presetFor(root?.dataset.theme);
  for (const selector of scope.querySelectorAll("[data-theme-select]")) selector.value = preset.id;
  const dark = preset.colorScheme === "dark";
  for (const button of scope.querySelectorAll("[data-theme-toggle]")) {
    button.setAttribute("aria-pressed", String(dark));
    button.setAttribute("aria-label", `Switch to ${dark ? "light" : "dark"} mode`);
    const label = button.querySelector("[data-theme-label]");
    if (label) label.textContent = `${dark ? "Light" : "Dark"} mode`;
    const icon = button.querySelector("[data-theme-icon]");
    if (icon) icon.textContent = dark ? "☀" : "☾";
  }
}

export function bindThemeToggleEvents({
  container = globalThis.document,
  root = globalThis.document?.documentElement,
  storage = getStorage(),
} = {}) {
  if (!container?.addEventListener) return;
  container.addEventListener("change", (event) => {
    const selector = event.target?.closest?.("[data-theme-select]");
    if (!selector) return;
    selectTheme(selector.value, { root, storage });
    syncThemeButtons(container, root);
  });
  container.addEventListener("click", (event) => {
    if (!event.target?.closest?.("[data-theme-toggle]")) return;
    toggleTheme({ root, storage });
    syncThemeButtons(container, root);
  });
}
