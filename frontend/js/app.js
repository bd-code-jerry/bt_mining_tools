import { authApi } from "./features/auth/api.js";
import { renderLoginPage, renderRegisterPage } from "./features/auth/page.js";
import { pageRegistry, resolvePage } from "./app/pageRegistry.js";
import { navigateTo, parseRouteHash } from "./app/router.js";
import { sidebarHtml } from "./shared/components/sidebar.js";
import { renderTimezoneSelector } from "./shared/components/timezoneSelector.js";
import { showToast } from "./shared/components/toast.js";
import { bindThemeToggleEvents, initializeTheme, syncThemeButtons } from "./theme.js";

const app = document.getElementById("app");
const state = { user: null, bootstrapped: false };
let activePageTimezoneChangeHandler = null;

initializeTheme();
bindThemeToggleEvents();

function go(route) {
  if (!navigateTo(route)) renderRoute();
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
  const route = parseRouteHash(window.location.hash, state.user ? "api-balances" : "login");
  if (route === "login") {
    if (state.user) return go("api-balances");
    renderLoginPage(app, {
      onSignedIn(user) {
        state.user = user;
        go("api-balances");
      },
    });
    syncThemeButtons(app);
    return;
  }
  if (route === "register") {
    if (state.user) return go("api-balances");
    await renderRegisterPage(app, {
      onSignedIn(user) {
        state.user = user;
        go("api-balances");
      },
    });
    syncThemeButtons(app);
    return;
  }
  if (!state.user) return go("login");

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
  await page.render(pageRoot, {
    onUnauthorized,
    user: state.user,
    registerTimezoneChangeHandler(handler) {
      activePageTimezoneChangeHandler = handler;
    },
  });
}

window.addEventListener("hashchange", renderRoute);

(async function start() {
  await bootstrapAuth();
  if (!window.location.hash) {
    window.location.hash = state.user ? "#/api-balances" : "#/login";
  }
  await renderRoute();
})();
