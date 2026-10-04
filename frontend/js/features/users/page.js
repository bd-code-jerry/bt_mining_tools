import { escapeHtml } from "../../shared/utils/format.js";
import { showToast } from "../../shared/components/toast.js";
import { usersApi } from "./api.js";
import { accountTableHtml, sessionListHtml } from "./components/accountTable.js";
import { pendingQueueHtml } from "./components/pendingQueue.js";
import { loginActivityHtml, userTimezoneLabel } from "./components/loginActivity.js";

const EMPTY_FILTERS = Object.freeze({ start_date: "", end_date: "", account_id: "", role: "" });

function formValue(form, name) {
  return form?.querySelector?.(`[name="${name}"]`)?.value ?? form?.elements?.namedItem?.(name)?.value ?? "";
}

function actionTarget(target) {
  return target?.closest?.("[data-action]") || target;
}

export function userManagementErrorHtml(message) {
  if (!message) return "";
  return `<div class="users-error" role="alert">${escapeHtml(message)}</div>`;
}

function createAccountFormHtml() {
  return `
    <form class="create-account-form" data-action="create-account">
      <label>Username<input class="input" name="username" autocomplete="off" required /></label>
      <label>Email<input class="input" type="email" name="email" autocomplete="off" required /></label>
      <label>Temporary password<input class="input" type="password" name="password" minlength="8" maxlength="256" autocomplete="new-password" required /></label>
      <label>Role<select class="input" name="role"><option value="member" selected>member</option><option value="user">user</option><option value="admin">admin</option></select></label>
      <button class="btn btn-primary" type="submit">Create account</button>
    </form>
  `;
}

function registrationControlHtml(enabled) {
  const state = enabled ? "Registration is open" : "Registration is closed";
  return `
    <label class="registration-control">
      <input type="checkbox" data-action="toggle-registration" ${enabled ? "checked" : ""} />
      <span><strong>${state}</strong><small>New self-registrations stay pending until approved.</small></span>
    </label>
  `;
}

function usersPageHtml({ accounts, registrationEnabled, filters, events, days, timezone, sessionUserId, sessions, error }) {
  const pending = accounts.filter((account) => account.status === "pending");
  const managed = accounts.filter((account) => account.status !== "pending");
  const sessionAccount = accounts.find((account) => Number(account.id) === Number(sessionUserId));
  return `
    <div class="users-page">
      <div class="page-heading users-page-heading">
        <div><h1>User management</h1><p class="page-subtitle">Approve accounts, manage access, and review sign-in history.</p></div>
        ${registrationControlHtml(registrationEnabled)}
      </div>
      ${userManagementErrorHtml(error)}

      <section class="card users-section-card">
        <div class="users-section-heading"><div><h2>Pending registrations</h2><p class="help">Choose a role when you approve an account.</p></div><span class="users-count-badge">${pending.length} waiting</span></div>
        ${pendingQueueHtml(pending)}
      </section>

      <section class="card users-section-card">
        <div class="users-section-heading"><div><h2>Accounts</h2><p class="help">Manage role, email, login access, sessions, and credentials.</p></div><span class="users-count-badge">${managed.length} accounts</span></div>
        ${accountTableHtml(managed)}
      </section>

      <section class="card users-section-card">
        <div class="users-section-heading"><div><h2>Create an account</h2><p class="help">Admin-created accounts are active immediately.</p></div></div>
        ${createAccountFormHtml()}
      </section>

      ${sessionUserId == null ? "" : `
        <div class="users-session-heading"><h2>Sessions for ${escapeHtml(sessionAccount?.username || `account #${sessionUserId}`)}</h2><button class="btn btn-small" type="button" data-action="close-sessions">Close</button></div>
        ${sessionListHtml(sessionUserId, sessions)}
      `}

      ${loginActivityHtml({ accounts, filters, events, days, timezone })}
    </div>
  `;
}

export async function renderUsersPage(container, {
  user,
  onUnauthorized,
  registerTimezoneChangeHandler,
  confirmAction = (message) => typeof globalThis.confirm === "function" && globalThis.confirm(message),
  notify = showToast,
} = {}) {
  const capabilities = new Set(user?.capabilities || []);
  if (!capabilities.has("users:manage")) {
    container.innerHTML = `<div class="card empty-state">This page is available to administrators only.</div>`;
    return;
  }

  let accounts = [];
  let registrationEnabled = true;
  let filters = { ...EMPTY_FILTERS };
  let events = [];
  let days = [];
  let timezone = user.timezone || "UTC";
  let sessionUserId = null;
  let sessions = [];
  let actionError = "";
  container.innerHTML = `<div class="loading-row">Loading user management…</div>`;

  const render = () => {
    container.innerHTML = usersPageHtml({
      accounts,
      registrationEnabled,
      filters,
      events,
      days,
      timezone,
      sessionUserId,
      sessions,
      error: actionError,
    });
  };

  const loadAccounts = async () => {
    const result = await usersApi.listAccounts();
    accounts = result.users || [];
    registrationEnabled = Boolean(result.registration_enabled);
  };

  const loadActivity = async () => {
    const [eventResult, dailyResult] = await Promise.all([
      usersApi.getLoginEvents(filters),
      usersApi.getDailyLoginCounts(filters),
    ]);
    events = eventResult.events || [];
    days = dailyResult.days || [];
    timezone = eventResult.timezone || dailyResult.timezone || timezone;
  };

  const loadSessions = async () => {
    if (sessionUserId == null) return;
    const result = await usersApi.getSessions(sessionUserId);
    sessions = result.sessions || [];
  };

  registerTimezoneChangeHandler?.(async (nextTimezone) => {
    timezone = nextTimezone;
    actionError = "";
    try {
      await loadActivity();
    } catch (error) {
      if (error.status === 401) {
        onUnauthorized?.();
        return;
      }
      actionError = error.message || "Unable to refresh login activity for this time zone.";
    }
    render();
  });

  const runAction = async (operation, { success = "", refreshAccounts = false, refreshSessions = false } = {}) => {
    actionError = "";
    try {
      await operation();
      if (refreshAccounts) await loadAccounts();
      if (refreshSessions) await loadSessions();
      if (success) notify(success, "success");
    } catch (error) {
      if (error.status === 401) {
        onUnauthorized?.();
        return;
      }
      actionError = error.message || "The request could not be completed.";
    }
    render();
  };

  try {
    await Promise.all([loadAccounts(), loadActivity()]);
    render();
  } catch (error) {
    if (error.status === 401) {
      onUnauthorized?.();
      return;
    }
    container.innerHTML = userManagementErrorHtml(error.message || "Unable to load user management.");
    return;
  }

  container.addEventListener("click", async (event) => {
    const target = actionTarget(event.target);
    const action = target?.dataset?.action;
    const userId = Number(target?.dataset?.userId);
    if (action === "deny-pending") {
      if (!confirmAction("Deny this registration and remove its pending account?")) return;
      await runAction(() => usersApi.denyPending(userId), { success: "Pending registration denied.", refreshAccounts: true });
    } else if (action === "delete-account") {
      if (!confirmAction("Delete this account and its private workspace data?")) return;
      await runAction(() => usersApi.deleteAccount(userId), { success: "Account deleted.", refreshAccounts: true });
    } else if (action === "toggle-status") {
      const status = target.dataset.nextStatus;
      if (status === "disabled" && !confirmAction("Disable this account and end its active sessions?")) return;
      await runAction(() => usersApi.setStatus(userId, status), { success: `Account ${status === "active" ? "enabled" : "disabled"}.`, refreshAccounts: true });
    } else if (action === "view-sessions") {
      sessionUserId = userId;
      sessions = [];
      await runAction(loadSessions);
    } else if (action === "revoke-user-sessions") {
      if (!confirmAction("Revoke all active sessions for this account?")) return;
      await runAction(() => usersApi.revokeSessions(userId), { success: "Active sessions revoked.", refreshSessions: Number(sessionUserId) === userId });
    } else if (action === "revoke-session") {
      const sessionId = Number(target.dataset.sessionId);
      if (!confirmAction("Revoke this active session?")) return;
      await runAction(() => usersApi.revokeSession(sessionId), { success: "Session revoked.", refreshSessions: true });
    } else if (action === "close-sessions") {
      sessionUserId = null;
      sessions = [];
      render();
    } else if (action === "clear-login-filters") {
      filters = { ...EMPTY_FILTERS };
      await runAction(loadActivity);
    }
  });

  container.addEventListener("change", async (event) => {
    const target = actionTarget(event.target);
    const action = target?.dataset?.action;
    const userId = Number(target?.dataset?.userId);
    if (action === "change-role") {
      await runAction(() => usersApi.setRole(userId, target.value), { success: "Account role updated.", refreshAccounts: true });
    } else if (action === "toggle-registration") {
      const enabled = Boolean(target.checked);
      await runAction(async () => {
        const result = await usersApi.setRegistrationEnabled(enabled);
        registrationEnabled = Boolean(result.registration_enabled);
      }, { success: enabled ? "Registration opened." : "Registration closed." });
    }
  });

  container.addEventListener("submit", async (event) => {
    const form = event.target;
    const action = form?.dataset?.action;
    if (!action) return;
    event.preventDefault?.();
    const userId = Number(form.dataset.userId);
    if (action === "approve-pending") {
      const role = formValue(form, "role") || "member";
      await runAction(() => usersApi.approvePending(userId, role), { success: "Account approved.", refreshAccounts: true });
    } else if (action === "create-account") {
      await runAction(() => usersApi.createAccount({
        username: formValue(form, "username").trim(),
        email: formValue(form, "email").trim(),
        password: formValue(form, "password"),
        role: formValue(form, "role") || "member",
      }), { success: "Account created.", refreshAccounts: true });
    } else if (action === "update-email") {
      await runAction(() => usersApi.updateEmail(userId, formValue(form, "email").trim()), { success: "Email updated.", refreshAccounts: true });
    } else if (action === "reset-password") {
      const passwordField = form.querySelector?.('[name="new_password"]');
      const newPassword = passwordField?.value ?? formValue(form, "new_password");
      if (passwordField) passwordField.value = "";
      await runAction(() => usersApi.resetPassword(userId, newPassword), { success: "Password reset and existing sessions ended." });
    } else if (action === "filter-login-activity") {
      filters = {
        start_date: formValue(form, "start_date"),
        end_date: formValue(form, "end_date"),
        account_id: formValue(form, "account_id"),
        role: formValue(form, "role"),
      };
      await runAction(loadActivity);
    }
  });
}

export { userTimezoneLabel };
