import test from "node:test";
import assert from "node:assert/strict";

import { initializeTheme, toggleTheme, syncThemeButtons } from "../frontend/js/theme.js";
import * as themeModule from "../frontend/js/theme.js";

function fakeStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    value(key) { return values.get(key); },
  };
}

function fakeRoot() {
  return { dataset: {}, style: { colorScheme: "" } };
}

test("initialization restores a saved dark theme on the document root", () => {
  const root = fakeRoot();
  const storage = fakeStorage({ "bd-dashboard-theme": "dark" });

  assert.equal(initializeTheme({ root, storage }), "dark");
  assert.equal(root.dataset.theme, "dark");
  assert.equal(root.style.colorScheme, "dark");
});

test("initialization falls back to light for an invalid saved preference", () => {
  const root = fakeRoot();
  const storage = fakeStorage({ "bd-dashboard-theme": "sepia" });

  assert.equal(initializeTheme({ root, storage }), "light");
  assert.equal(root.dataset.theme, "light");
});

test("toggling changes the theme and saves the new preference", () => {
  const root = fakeRoot();
  const storage = fakeStorage();
  initializeTheme({ root, storage });

  assert.equal(toggleTheme({ root, storage }), "dark");
  assert.equal(root.dataset.theme, "dark");
  assert.equal(storage.value("bd-dashboard-theme"), "dark");
  assert.equal(toggleTheme({ root, storage }), "light");
  assert.equal(storage.value("bd-dashboard-theme"), "light");
});

test("theme still changes when browser storage is unavailable", () => {
  const root = fakeRoot();
  const storage = {
    getItem() { throw new Error("Storage blocked"); },
    setItem() { throw new Error("Storage blocked"); },
  };

  assert.equal(initializeTheme({ root, storage }), "light");
  assert.equal(toggleTheme({ root, storage }), "dark");
  assert.equal(root.dataset.theme, "dark");
});

test("theme buttons describe the mode they will switch to", () => {
  const originalDocument = globalThis.document;
  const attrs = {};
  const label = { textContent: "" };
  const icon = { textContent: "" };
  const button = {
    setAttribute(key, value) { attrs[key] = value; },
    querySelector(selector) {
      if (selector === "[data-theme-label]") return label;
      if (selector === "[data-theme-icon]") return icon;
      return null;
    },
  };
  globalThis.document = { documentElement: { dataset: { theme: "dark" } } };
  try {
    syncThemeButtons({ querySelectorAll: (selector) => selector === "[data-theme-toggle]" ? [button] : [] });
    assert.equal(attrs["aria-pressed"], "true");
    assert.equal(attrs["aria-label"], "Switch to light mode");
    assert.equal(label.textContent, "Light mode");
    assert.equal(icon.textContent, "☀");
  } finally {
    globalThis.document = originalDocument;
  }
});

test("clicking the theme button changes the page, saves it, and updates its label", () => {
  assert.equal(typeof themeModule.bindThemeToggleEvents, "function");
  const root = fakeRoot();
  const storage = fakeStorage();
  const attrs = {};
  const label = { textContent: "Dark mode" };
  const icon = { textContent: "☾" };
  const button = {
    setAttribute(key, value) { attrs[key] = value; },
    querySelector(selector) {
      if (selector === "[data-theme-label]") return label;
      if (selector === "[data-theme-icon]") return icon;
      return null;
    },
  };
  let clickHandler;
  const container = {
    addEventListener(type, handler) {
      if (type === "click") clickHandler = handler;
    },
    querySelectorAll: (selector) => selector === "[data-theme-toggle]" ? [button] : [],
  };
  initializeTheme({ root, storage });
  themeModule.bindThemeToggleEvents({ container, root, storage });
  clickHandler({ target: { closest: (selector) => selector === "[data-theme-toggle]" ? button : null } });

  assert.equal(root.dataset.theme, "dark");
  assert.equal(storage.value("bd-dashboard-theme"), "dark");
  assert.equal(attrs["aria-pressed"], "true");
  assert.equal(attrs["aria-label"], "Switch to light mode");
  assert.equal(label.textContent, "Light mode");
  assert.equal(icon.textContent, "☀");
});

for (const [theme, scheme] of [["light", "light"], ["dark", "dark"], ["sand", "light"], ["forest", "dark"], ["midnight", "dark"]]) {
  test(`selection and startup restore ${theme} with native ${scheme} scheme`, () => {
    assert.equal(typeof themeModule.selectTheme, "function");
    const root = fakeRoot();
    const storage = fakeStorage();
    assert.equal(themeModule.selectTheme(theme, { root, storage }), theme);
    assert.equal(root.dataset.theme, theme);
    assert.equal(root.style.colorScheme, scheme);
    assert.equal(storage.value("bd-dashboard-theme"), theme);
    const restored = fakeRoot();
    assert.equal(initializeTheme({ root: restored, storage }), theme);
    assert.equal(restored.style.colorScheme, scheme);
  });
}

test("preset selection handles invalid IDs and blocked storage", () => {
  assert.equal(typeof themeModule.selectTheme, "function");
  const root = fakeRoot();
  const storage = { setItem() { throw new Error("blocked"); } };
  assert.equal(themeModule.selectTheme("forest", { root, storage }), "forest");
  assert.equal(root.style.colorScheme, "dark");
  assert.equal(themeModule.selectTheme("unknown", { root, storage }), "light");
});

test("delegated selector change persists appearance and synchronizes rerendered controls", () => {
  const root = fakeRoot();
  const storage = fakeStorage();
  const first = { value: "light" };
  let selectors = [first];
  const handlers = {};
  const container = {
    addEventListener(type, handler) { handlers[type] = handler; },
    querySelectorAll(selector) { return selector === "[data-theme-select]" ? selectors : []; },
  };
  themeModule.bindThemeToggleEvents({ container, root, storage });
  assert.equal(typeof handlers.change, "function");
  first.value = "midnight";
  handlers.change({ target: { closest: () => first } });
  assert.equal(root.dataset.theme, "midnight");
  assert.equal(storage.value("bd-dashboard-theme"), "midnight");
  const rerendered = { value: "light" };
  selectors = [first, rerendered];
  syncThemeButtons(container, root);
  assert.equal(rerendered.value, "midnight");
});
