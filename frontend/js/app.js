import { authApi } from "./features/auth/api.js";
import { renderLoginPage, renderRegisterPage } from "./features/auth/page.js";
import { pageRegistry, resolvePage } from "./app/pageRegistry.js";
import { navigateTo, parseRouteHash } from "./app/router.js";
import { sidebarHtml } from "./shared/components/sidebar.js";
import { renderTimezoneSelector } from "./shared/components/timezoneSelector.js";
import { showToast } from "./shared/components/toast.js";
import { bindThemeToggleEvents, initializeTheme, syncThemeButtons } from "./theme.js";

const APP_VERSION = "1.3.1";
const app = document.getElementById("app");
const state = { user: null, bootstrapped: false };
let activePageTimezoneChangeHandler = null;

initializeTheme();
bindThemeToggleEvents();

function go(route) {
  if (!navigateTo(route)) renderRoute();
}

function reloadDashboard() {
  const url = new URL(window.location.pathname, window.location.origin);
  url.searchParams.set("v", APP_VERSION);
  url.hash = "#/overview";
  if (url.href === window.location.href) window.location.reload();
  else window.location.replace(url.href);
}

function renderUpdateRecovery(pageCouldNotLoad = false) {
  activePageTimezoneChangeHandler = null;
  app.innerHTML = `
    <main class="main" aria-labelledby="update-title">
      <div class="card" role="alert">
        <h1 id="update-title">Dashboard update incomplete</h1>
        <p>${pageCouldNotLoad ? "The dashboard page could not load. Some files may be missing or outdated." : "The running dashboard and browser files do not support the same pages."}</p>
        <p>Stop the dashboard, copy all ZIP files into the existing project, and restart the updated project. Then reload this page.</p>
        <button class="btn btn-primary" type="button" data-update-reload>Reload dashboard</button>
        <p class="muted">App version ${APP_VERSION}</p>
      </div>
    </main>
  `;
  app.querySelector("[data-update-reload]")?.addEventListener("click", reloadDashboard);
}

async function bootstrapAuth() {
  try {
    const result = await authApi.me();
    state.user = result.user;
  } catch (error) {
    if (error.status !== 401) showToast(error.message, "error");
    state.user = null;
  } finally {
    state.bootstrapped = true;
  }
}

function protectedShell(activeRoute) {
  activePageTimezoneChangeHandler = null;
  app.innerHTML = `
    <div class="app-shell">
      ${sidebarHtml(activeRoute, state.user)}
      <main class="main" id="page-root"></main>
    </div>
  `;
  syncThemeButtons(app);
  const timezoneRoot = app.querySelector("[data-timezone-selector-root]");
  renderTimezoneSelector(timezoneRoot, {
    timezone: state.user.timezone || "UTC",
    async onUpdated(timezone) {
      state.user = { ...state.user, timezone };
      await activePageTimezoneChangeHandler?.(timezone);
    },
  });

  app.querySelector("[data-logout]")?.addEventListener("click", async () => {
    try { await authApi.logout(); } catch (_) {}
    state.user = null;
    go("login");
  });
  return document.getElementById("page-root");
}

async function renderRoute() {
  if (!state.bootstrapped) return;
  const route = parseRouteHash(window.location.hash, state.user ? "overview" : "login");
  if (route === "login") {
    if (state.user) return go("overview");
    renderLoginPage(app, {
      onSignedIn(user) {
        state.user = user;
        go("overview");
      },
    });
    syncThemeButtons(app);
    return;
  }
  if (route === "register") {
    if (state.user) return go("overview");
    await renderRegisterPage(app, {
      onSignedIn(user) {
        state.user = user;
        go("overview");
      },
    });
    syncThemeButtons(app);
    return;
  }
  if (!state.user) return go("login");

  if (!state.user.capabilities?.includes("expenses:read") ||
      !["overview", "used"].every((requiredRoute) => pageRegistry.some((page) => page.route === requiredRoute))) {
    renderUpdateRecovery();
    return;
  }

  const page = resolvePage(route, state.user, pageRegistry);
  if (!page) {
    app.innerHTML = `<main class="main"><div class="empty-state">This account has no pages available.</div></main>`;
    return;
  }
  if (route !== page.route) return go(page.route);

  const pageRoot = protectedShell(page.route);
  const onUnauthorized = () => {
    state.user = null;
    go("login");
  };
  try {
    await page.render(pageRoot, {
      onUnauthorized,
      user: state.user,
      registerTimezoneChangeHandler(handler) {
        activePageTimezoneChangeHandler = handler;
      },
    });
  } catch (error) {
    if (pageRoot.isConnected === false) return;
    if (error?.status === 401) onUnauthorized();
    else renderUpdateRecovery(true);
  }
}

window.addEventListener("hashchange", renderRoute);

(async function start() {
  await bootstrapAuth();
  if (!window.location.hash) {
    window.location.hash = state.user ? "#/overview" : "#/login";
  }
  await renderRoute();
})();
