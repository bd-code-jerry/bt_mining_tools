import test from "node:test";
import assert from "node:assert/strict";

import { pageRegistry, visiblePages } from "../frontend/js/app/pageRegistry.js";
import { usersApi } from "../frontend/js/features/users/api.js";
import { renderUsersPage, userManagementErrorHtml } from "../frontend/js/features/users/page.js";
import { accountTableHtml, resetPasswordFormHtml, sessionListHtml } from "../frontend/js/features/users/components/accountTable.js";
import { pendingQueueHtml } from "../frontend/js/features/users/components/pendingQueue.js";
import { loginActivityHtml, userTimezoneLabel } from "../frontend/js/features/users/components/loginActivity.js";

const admin = { id: 1, role: "admin", timezone: "America/New_York", capabilities: ["users:manage"] };
const account = {
  id: 12,
  username: "<img src=x onerror=alert(1)>",
  email: "person@example.com",
  role: "member",
  status: "active",
  created_at: "2030-01-01T09:00:00-05:00",
  last_login_at: "2030-01-02T08:00:00-05:00",
  password_hash: "stored-hash-must-not-render",
  password: "old-password-must-not-render",
};

function withFetch(callback) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return {
      ok: true,
      headers: { get: () => "application/json" },
      async json() { return { ok: true }; },
    };
  };
  return Promise.resolve().then(() => callback(calls)).finally(() => { globalThis.fetch = originalFetch; });
}

function testContainer() {
  return { innerHTML: "", listeners: {}, addEventListener(type, listener) { this.listeners[type] = listener; } };
}

function testForm(action, userId, values) {
  return {
    dataset: { action, userId: String(userId) },
    querySelector(selector) {
      const name = selector.match(/\[name="([^"]+)"\]/)?.[1];
      if (!name) return null;
      return values[name] || null;
    },
  };
}

async function withUsersApi(overrides, callback) {
  const originals = Object.fromEntries(Object.keys(overrides).map((key) => [key, usersApi[key]]));
  Object.assign(usersApi, overrides);
  try { await callback(); } finally { Object.assign(usersApi, originals); }
}

test("only admins with users:manage see the Users page", () => {
  const user = { role: "user", capabilities: ["balances:read", "total_balances:read"] };
  const member = { role: "member", capabilities: ["balances:read", "total_balances:read"] };
  const authorizedAdmin = { ...admin, capabilities: ["users:manage"] };

  assert.equal(pageRegistry.find((page) => page.route === "users")?.capability, "users:manage");
  assert.equal(visiblePages(user).some((page) => page.route === "users"), false);
  assert.equal(visiblePages(member).some((page) => page.route === "users"), false);
  assert.equal(visiblePages(authorizedAdmin).some((page) => page.route === "users"), true);
});

test("pending queue exposes approve-with-role and deny actions", () => {
  const html = pendingQueueHtml([{
    id: 20,
    username: "pending-one",
    email: "pending@example.com",
    created_at: "2030-01-01T10:00:00-05:00",
  }]);

  assert.match(html, /data-action="approve-pending"/);
  assert.match(html, /data-action="deny-pending"/);
  assert.match(html, /name="role"/);
  assert.match(html, /value="user"/);
});

test("account controls show status, role, email and login dates without exposing stored secrets", () => {
  const html = accountTableHtml([account]);

  assert.match(html, /data-action="change-role"/);
  assert.match(html, /data-action="toggle-status"/);
  assert.match(html, /data-action="update-email"/);
  assert.match(html, /2030-01-02T08:00:00-05:00/);
  assert.match(html, /data-action="delete-account"/);
  assert.doesNotMatch(html, /stored-hash-must-not-render|old-password-must-not-render/);
});

test("password reset starts blank and active sessions can be listed/revoked without secret fields", () => {
  const form = resetPasswordFormHtml(12);
  assert.match(form, /type="password"/);
  assert.match(form, /name="new_password"/);
  assert.doesNotMatch(form, /value=/);
  assert.match(form, /data-action="reset-password"/);

  const sessions = sessionListHtml(12, [{
    id: 31,
    created_at: "2030-01-02T08:00:00-05:00",
    last_activity_at: "2030-01-02T08:10:00-05:00",
    expires_at: "2030-01-16T08:00:00-05:00",
    token: "never-render-this",
    ip_address: "never-render-this-either",
  }]);
  assert.match(sessions, /data-action="revoke-session"/);
  assert.match(sessions, /data-action="revoke-user-sessions"/);
  assert.doesNotMatch(sessions, /never-render-this|ip_address|token/);
});

test("login activity includes account/date/role filters and daily counts in the selected timezone", () => {
  const html = loginActivityHtml({
    accounts: [account],
    filters: { start_date: "2030-01-01", end_date: "2030-01-02", account_id: "12", role: "member" },
    events: [{ user_id: 12, username: "person", email: "person@example.com", role: "member", signed_in_at: "2030-01-02T08:00:00-05:00" }],
    days: [{ date: "2030-01-01", count: 2 }, { date: "2030-01-02", count: 1 }],
    timezone: "America/New_York",
  });
  assert.match(html, /name="start_date" value="2030-01-01"/);
  assert.match(html, /name="end_date" value="2030-01-02"/);
  assert.match(html, /name="account_id"/);
  assert.match(html, /name="role"/);
  assert.match(html, /2 sign-ins/);
  assert.match(html, /2030-01-02T08:00:00-05:00/);
  assert.match(html, /Eastern Time \(ET\)/);
  assert.match(html, /prior 30 days/);
  assert.equal(userTimezoneLabel("UTC"), "UTC");
});

test("users API sends role/date/account filters to event and daily-count endpoints", async () => {
  await withFetch(async (calls) => {
    const filters = { start_date: "2030-01-01", end_date: "2030-01-02", account_id: 12, role: "member" };
    await usersApi.getLoginEvents(filters);
    await usersApi.getDailyLoginCounts(filters);
    assert.equal(calls.length, 2);
    assert.equal(new URL(calls[0].url, "http://localhost").pathname, "/api/users/login-events");
    assert.equal(new URL(calls[1].url, "http://localhost").pathname, "/api/users/login-events/daily");
    for (const { url } of calls) {
      const query = new URL(url, "http://localhost").searchParams;
      assert.equal(query.get("start_date"), "2030-01-01");
      assert.equal(query.get("end_date"), "2030-01-02");
      assert.equal(query.get("account_id"), "12");
      assert.equal(query.get("role"), "member");
    }
  });
});

test("users API maps account, approval, registration, session and password actions to admin endpoints", async () => {
  await withFetch(async (calls) => {
    await usersApi.approvePending(20, "user");
    await usersApi.denyPending(20);
    await usersApi.setRole(12, "admin");
    await usersApi.setStatus(12, "disabled");
    await usersApi.resetPassword(12, "new-password-123");
    await usersApi.deleteAccount(12);
    await usersApi.getSessions(12);
    await usersApi.revokeSessions(12);
    await usersApi.revokeSession(31);
    await usersApi.setRegistrationEnabled(false);

    assert.deepEqual(calls.map((call) => [call.options.method || "GET", new URL(call.url, "http://localhost").pathname]), [
      ["POST", "/api/users/pending/20/approve"],
      ["DELETE", "/api/users/pending/20"],
      ["PATCH", "/api/users/12/role"],
      ["PATCH", "/api/users/12/status"],
      ["POST", "/api/users/12/password-reset"],
      ["DELETE", "/api/users/12"],
      ["GET", "/api/users/12/sessions"],
      ["DELETE", "/api/users/12/sessions"],
      ["DELETE", "/api/users/sessions/31"],
      ["PATCH", "/api/users/registration"],
    ]);
    assert.deepEqual(JSON.parse(calls[0].options.body), { role: "user" });
    assert.deepEqual(JSON.parse(calls[4].options.body), { new_password: "new-password-123" });
    assert.deepEqual(JSON.parse(calls[9].options.body), { enabled: false });
  });
});

test("deny requires confirmation and approval submits the selected role", async () => {
  const calls = [];
  let allowConfirmation = false;
  await withUsersApi({
    listAccounts: async () => ({ users: [{ id: 20, username: "pending", email: "pending@example.com", status: "pending" }], registration_enabled: true }),
    getLoginEvents: async () => ({ timezone: "UTC", events: [] }),
    getDailyLoginCounts: async () => ({ timezone: "UTC", days: [] }),
    denyPending: async (id) => calls.push(["deny", id]),
    approvePending: async (id, role) => calls.push(["approve", id, role]),
  }, async () => {
    const container = testContainer();
    await renderUsersPage(container, { user: admin, confirmAction: () => allowConfirmation, notify() {} });
    await container.listeners.click({ target: { dataset: { action: "deny-pending", userId: "20" } } });
    assert.deepEqual(calls, []);
    allowConfirmation = true;
    await container.listeners.click({ target: { dataset: { action: "deny-pending", userId: "20" } } });
    await container.listeners.submit({
      target: testForm("approve-pending", 20, { role: { value: "user" } }),
      preventDefault() {},
    });
    assert.deepEqual(calls, [["deny", 20], ["approve", 20, "user"]]);
  });
});

test("role and status controls update the account and deletion requires confirmation", async () => {
  const calls = [];
  await withUsersApi({
    listAccounts: async () => ({ users: [{ ...account }], registration_enabled: true }),
    getLoginEvents: async () => ({ timezone: "UTC", events: [] }),
    getDailyLoginCounts: async () => ({ timezone: "UTC", days: [] }),
    setRole: async (id, role) => calls.push(["role", id, role]),
    setStatus: async (id, status) => calls.push(["status", id, status]),
    deleteAccount: async (id) => calls.push(["delete", id]),
  }, async () => {
    const container = testContainer();
    await renderUsersPage(container, { user: admin, confirmAction: () => false, notify() {} });
    await container.listeners.change({ target: { dataset: { action: "change-role", userId: "12" }, value: "user" } });
    await container.listeners.click({ target: { dataset: { action: "toggle-status", userId: "12", nextStatus: "disabled" } } });
    await container.listeners.click({ target: { dataset: { action: "delete-account", userId: "12" } } });
    assert.deepEqual(calls, [["role", 12, "user"]]);
  });
});

test("duplicate creation errors stay visible and password inputs clear after a reset", async () => {
  const duplicate = new Error("That username or email address is already in use.");
  duplicate.status = 409;
  const passwordField = { value: "new-password-123", setAttribute(name, value) { this.attributes ??= {}; this.attributes[name] = value; } };
  const createForm = testForm("create-account", 0, {
    username: { value: "duplicate" },
    email: { value: "person@example.com" },
    password: { value: "new-password-123" },
    role: { value: "member" },
  });
  const resetForm = testForm("reset-password", 12, { new_password: passwordField });
  await withUsersApi({
    listAccounts: async () => ({ users: [{ ...account }], registration_enabled: true }),
    getLoginEvents: async () => ({ timezone: "UTC", events: [] }),
    getDailyLoginCounts: async () => ({ timezone: "UTC", days: [] }),
    createAccount: async () => { throw duplicate; },
    resetPassword: async () => ({ ok: true }),
  }, async () => {
    const container = testContainer();
    await renderUsersPage(container, { user: admin, notify() {} });
    await container.listeners.submit({ target: createForm, preventDefault() {} });
    assert.match(container.innerHTML, /That username or email address is already in use\./);
    await container.listeners.submit({ target: resetForm, preventDefault() {} });
    assert.equal(passwordField.value, "");
  });
});

test("login filters are applied to both persisted event and daily-count requests", async () => {
  let eventFilters;
  let dailyFilters;
  await withUsersApi({
    listAccounts: async () => ({ users: [{ ...account }], registration_enabled: true }),
    getLoginEvents: async (filters) => { eventFilters = filters; return { timezone: "UTC", events: [] }; },
    getDailyLoginCounts: async (filters) => { dailyFilters = filters; return { timezone: "UTC", days: [] }; },
  }, async () => {
    const container = testContainer();
    await renderUsersPage(container, { user: admin, notify() {} });
    await container.listeners.submit({
      target: testForm("filter-login-activity", 0, {
        start_date: { value: "2030-01-01" },
        end_date: { value: "2030-01-02" },
        account_id: { value: "12" },
        role: { value: "member" },
      }),
      preventDefault() {},
    });
    const expected = { start_date: "2030-01-01", end_date: "2030-01-02", account_id: "12", role: "member" };
    assert.deepEqual(eventFilters, expected);
    assert.deepEqual(dailyFilters, expected);
  });
});

test("admin users page loads pending accounts and login data using the viewer timezone", async () => {
  const originals = {
    listAccounts: usersApi.listAccounts,
    getLoginEvents: usersApi.getLoginEvents,
    getDailyLoginCounts: usersApi.getDailyLoginCounts,
  };
  usersApi.listAccounts = async () => ({ users: [{ ...account, status: "pending" }], registration_enabled: true });
  usersApi.getLoginEvents = async () => ({ timezone: admin.timezone, events: [] });
  usersApi.getDailyLoginCounts = async () => ({ timezone: admin.timezone, days: [{ date: "2030-01-02", count: 1 }] });
  const container = { innerHTML: "", listeners: {}, addEventListener(type, listener) { this.listeners[type] = listener; } };
  try {
    await renderUsersPage(container, { user: admin, notify() {} });
    assert.match(container.innerHTML, /User management/);
    assert.match(container.innerHTML, /pending-one|&lt;img/);
    assert.match(container.innerHTML, /Registration is open/);
    assert.match(container.innerHTML, /America\/New_York|Eastern Time/);
    assert.equal(typeof container.listeners.submit, "function");
    assert.equal(typeof container.listeners.click, "function");
  } finally {
    Object.assign(usersApi, originals);
  }
});

test("changing the timezone reloads login reports while preserving filters and selected sessions", async () => {
  const calls = { events: [], daily: [], sessionIds: [] };
  let currentTimezone = "UTC";
  let refreshTimezone;
  await withUsersApi({
    listAccounts: async () => ({ users: [{ ...account }], registration_enabled: true }),
    getLoginEvents: async (filters) => {
      calls.events.push({ ...filters });
      return { timezone: currentTimezone, events: [{ ...account, signed_in_at: "2030-01-02T08:00:00-05:00" }] };
    },
    getDailyLoginCounts: async (filters) => {
      calls.daily.push({ ...filters });
      return { timezone: currentTimezone, days: [{ date: "2030-01-02", count: currentTimezone === "UTC" ? 1 : 2 }] };
    },
    getSessions: async (id) => {
      calls.sessionIds.push(id);
      return { sessions: [{ id: 31, created_at: "2030-01-02T08:00:00-05:00", last_activity_at: "2030-01-02T08:10:00-05:00", expires_at: "2030-01-16T08:00:00-05:00" }] };
    },
  }, async () => {
    const container = testContainer();
    await renderUsersPage(container, {
      user: admin,
      notify() {},
      registerTimezoneChangeHandler(handler) { refreshTimezone = handler; },
    });
    const filters = { start_date: "2030-01-01", end_date: "2030-01-02", account_id: "12", role: "member" };
    await container.listeners.submit({
      target: testForm("filter-login-activity", 0, {
        start_date: { value: filters.start_date },
        end_date: { value: filters.end_date },
        account_id: { value: filters.account_id },
        role: { value: filters.role },
      }),
      preventDefault() {},
    });
    await container.listeners.click({ target: { dataset: { action: "view-sessions", userId: "12" } } });

    currentTimezone = "America/New_York";
    await refreshTimezone(currentTimezone);

    assert.deepEqual(calls.events.at(-1), filters);
    assert.deepEqual(calls.daily.at(-1), filters);
    assert.deepEqual(calls.sessionIds, [12]);
    assert.match(container.innerHTML, /Eastern Time \(ET\)/);
    assert.match(container.innerHTML, /Sessions for &lt;img src=x onerror=alert\(1\)&gt;/);
    assert.match(container.innerHTML, /2 sign-ins/);
  });
});

test("duplicate account errors are displayed clearly and escaped", () => {
  const html = userManagementErrorHtml("That username or email address is already in use.");
  assert.match(html, /That username or email address is already in use\./);
  assert.match(userManagementErrorHtml("<script>alert(1)</script>"), /&lt;script&gt;/);
  assert.doesNotMatch(userManagementErrorHtml("<script>alert(1)</script>"), /<script>/);
});
