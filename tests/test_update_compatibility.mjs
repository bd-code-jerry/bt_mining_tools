import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { pageRegistry, resolvePage } from "../frontend/js/app/pageRegistry.js";
import { navigateTo, parseRouteHash } from "../frontend/js/app/router.js";
import { sidebarHtml } from "../frontend/js/shared/components/sidebar.js";

const source = (await readFile(new URL("../frontend/js/app.js", import.meta.url), "utf8"))
  .replace(/^import .*;$/gm, "");
const currentUser = {
  id: 1, username: "admin", email: "admin@example.com", role: "admin", status: "active", timezone: "UTC",
  capabilities: ["expenses:read", "balances:read", "total_balances:read", "users:manage"],
};

async function boot({ user = currentUser, registry = pageRegistry, pageError = null, href = "http://localhost:8765/#/overview" } = {}) {
  const initialUrl = new URL(href);
  let reloads = 0;
  const replacements = [];
  const location = {
    href: initialUrl.href, origin: initialUrl.origin, pathname: initialUrl.pathname,
    search: initialUrl.search, hash: initialUrl.hash,
    replace(target) { replacements.push(target); },
    reload() { reloads++; },
  };
  let reloadHandler;
  const reloadButton = { addEventListener(name, handler) { if (name === "click") reloadHandler = handler; } };
  const app = {
    innerHTML: "",
    querySelector(selector) {
      return selector === "[data-update-reload]" && this.innerHTML.includes("data-update-reload") ? reloadButton : null;
    },
  };
  const pageRoot = { innerHTML: "" };
  const pages = registry.map(page => ({ ...page, async render(container) {
    if (pageError) throw pageError;
    container.innerHTML = `<h1>${page.label}</h1>`;
  } }));
  const context = {
    URL, document: { getElementById(id) { return id === "app" ? app : pageRoot; } },
    window: { location, addEventListener() {} },
    authApi: { async me() {
      if (!user) throw Object.assign(new Error("Unauthenticated"), { status: 401 });
      return { user };
    } },
    initializeTheme() {}, bindThemeToggleEvents() {}, syncThemeButtons() {}, renderTimezoneSelector() {}, showToast() {},
    renderLoginPage(container) { container.innerHTML = "<h1>Sign in</h1>"; },
    renderRegisterPage() {}, sidebarHtml, parseRouteHash,
    navigateTo(route) { const changed = navigateTo(route, location); return changed ? false : changed; },
    resolvePage, pageRegistry: pages,
  };
  let startupError = null;
  try { await vm.runInNewContext(source, context); } catch (error) { startupError = error; }
  return { app, pageRoot, location, replacements, get reloads() { return reloads; }, startupError,
    clickReload() { assert.ok(reloadHandler, "recovery action must be operable"); reloadHandler(); } };
}

for (const role of ["admin", "member", "user"]) {
  test(`a ${role} session from the old backend shows recovery instead of silently hiding expense pages`, async () => {
    const user = { ...currentUser, role, capabilities: ["balances:read", "total_balances:read"] };
    const session = await boot({ user, href: "http://localhost:8765/#/api-balances" });
    assert.equal(session.startupError, null);
    assert.match(session.app.innerHTML, /Dashboard update incomplete/);
    assert.match(session.app.innerHTML, /Restart[\s\S]*updated project/i);
    assert.match(session.app.innerHTML, /all[\s\S]*ZIP files/i);
    assert.match(session.app.innerHTML, /1\.3\.1/);
    assert.match(session.app.innerHTML, /<button[^>]*type="button"[^>]*data-update-reload/);
    assert.doesNotMatch(session.app.innerHTML, /class="app-shell"/);
    assert.deepEqual(user.capabilities, ["balances:read", "total_balances:read"]);
  });
}

for (const missing of ["overview", "used"]) {
  test(`a cached registry missing ${missing} shows the update recovery screen`, async () => {
    const session = await boot({ registry: pageRegistry.filter(page => page.route !== missing) });
    assert.match(session.app.innerHTML, /Dashboard update incomplete/);
    assert.doesNotMatch(session.app.innerHTML, /class="app-shell"/);
  });
}

test("recovery reload navigates to the current project with the repair version", async () => {
  const session = await boot({ user: { ...currentUser, capabilities: [] }, href: "http://localhost:8765/dashboard/?old=1#/api-balances" });
  session.clickReload();
  assert.deepEqual(session.replacements, ["http://localhost:8765/dashboard/?v=1.3.1#/overview"]);
});

test("recovery reload refreshes when the repair URL is already current", async () => {
  const session = await boot({ user: { ...currentUser, capabilities: [] }, href: "http://localhost:8765/?v=1.3.1#/overview" });
  session.clickReload();
  assert.equal(session.reloads, 1);
});

test("an authenticated compatible session still opens the requested authorized page", async () => {
  const session = await boot({ href: "http://localhost:8765/#/total-balances" });
  assert.equal(session.startupError, null);
  assert.match(session.app.innerHTML, /class="app-shell"/);
  assert.equal(session.pageRoot.innerHTML, "<h1>Total Balance</h1>");
  assert.doesNotMatch(session.app.innerHTML, /Dashboard update incomplete/);
});

test("signed-out sessions continue to display sign-in", async () => {
  const session = await boot({ user: null });
  assert.equal(session.startupError, null);
  assert.equal(session.app.innerHTML, "<h1>Sign in</h1>");
});

test("a failed page import displays recovery instead of leaving an unhandled blank page", async () => {
  const session = await boot({ pageError: new TypeError("Failed to fetch dynamically imported module") });
  assert.equal(session.startupError, null);
  assert.match(session.app.innerHTML, /Dashboard update incomplete/);
  assert.match(session.app.innerHTML, /page could not load/i);
  session.clickReload();
  assert.deepEqual(session.replacements, ["http://localhost:8765/?v=1.3.1#/overview"]);
});

test("a page authentication failure still returns to sign-in", async () => {
  const session = await boot({ pageError: Object.assign(new Error("Expired session"), { status: 401 }) });
  assert.equal(session.startupError, null);
  assert.equal(session.app.innerHTML, "<h1>Sign in</h1>");
});
