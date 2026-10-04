import test from "node:test";
import assert from "node:assert/strict";

import { balancesApi } from "../frontend/js/features/balances/api.js";
import { balancePagePermissions, chooseWorkspaceForRole, workspaceContextHtml } from "../frontend/js/features/balances/page.js";
import { balanceHistoryTableHtml } from "../frontend/js/features/balances/components/history.js";
import { workspaceSelectorHtml } from "../frontend/js/features/workspaces/components/workspaceSelector.js";
import { preferencesApi } from "../frontend/js/features/preferences/api.js";
import { createWorkspaceDataController } from "../frontend/js/features/balances/workspaceData.js";

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

test("balance write controls are capability-based and workspace choices respect each role", () => {
  const workspaces = [
    { id: 1, kind: "shared", display_name: "Shared workspace", owner_user_id: null },
    { id: 2, kind: "private", display_name: "mine", owner_user_id: 8 },
    { id: 3, kind: "private", display_name: "other", owner_user_id: 9 },
  ];
  const admin = { id: 1, role: "admin", capabilities: ["balances:read", "balances:write", "workspaces:manage"] };
  const member = { id: 7, role: "member", capabilities: ["balances:read"] };
  const user = { id: 8, role: "user", capabilities: ["balances:read", "balances:write"] };

  assert.deepEqual(balancePagePermissions(admin), { canWrite: true, canSelectWorkspace: true });
  assert.deepEqual(balancePagePermissions(member), { canWrite: false, canSelectWorkspace: false });
  assert.deepEqual(balancePagePermissions(user), { canWrite: true, canSelectWorkspace: false });
  assert.equal(chooseWorkspaceForRole(admin, workspaces, 3).id, 3);
  assert.equal(chooseWorkspaceForRole(member, workspaces, 3).id, 1);
  assert.equal(chooseWorkspaceForRole(user, workspaces, 3).id, 2);
  assert.match(workspaceSelectorHtml({ role: "admin", workspaces, selectedWorkspaceId: 3 }), /value="3" selected/);
  assert.equal(workspaceSelectorHtml({ role: "member", workspaces, selectedWorkspaceId: 1 }), "");
  assert.match(workspaceContextHtml(workspaces[1]), /mine/);
});

test("members see read-only history while admins and users can see edit controls", () => {
  const overview = {
    providers: [{ provider_key: "openrouter", display_name: "OpenRouter", unit: "USD" }],
    history: [{
      id: 3,
      entry_date: "2030-01-02",
      values: [{ provider_key: "openrouter", used_balance: 2, left_balance: 8 }],
    }],
    pagination: { page: 1, total_pages: 1, page_size: 5, total_items: 1 },
  };

  const memberHtml = balanceHistoryTableHtml(overview, { canWrite: false });
  const adminHtml = balanceHistoryTableHtml(overview, { canWrite: true });

  assert.doesNotMatch(memberHtml, /data-edit-entry|data-delete-entry|<th>Actions<\/th>/);
  assert.match(adminHtml, /data-edit-entry="3"/);
  assert.match(adminHtml, /data-delete-entry="3"/);
});

test("balance overview and mutations include the selected workspace ID", async () => {
  await withFetch(async (calls) => {
    await balancesApi.getOverview(2, 10, 42);
    await balancesApi.getOverview(1, 5, 2);
    await balancesApi.getOverview(1, 5, 3);
    await balancesApi.getHistoryEntry(5, 42);
    await balancesApi.createHistory({ entry_date: "2030-01-02", values: {} }, 42);
    await balancesApi.addBalances({ entry_date: "2030-01-02", additions: {} }, 42);
    await balancesApi.updateHistory(5, { entry_date: "2030-01-03", values: {} }, 42);
    await balancesApi.deleteHistory(5, 42);
    assert.equal(calls.length, 8);
    assert.ok(calls.slice(3).every((call) => new URL(call.url, "http://localhost").searchParams.get("workspace_id") === "42"));
    assert.equal(new URL(calls[1].url, "http://localhost").searchParams.get("workspace_id"), "2");
    assert.equal(new URL(calls[2].url, "http://localhost").searchParams.get("workspace_id"), "3");
    assert.equal(JSON.parse(calls[4].options.body).entry_date, "2030-01-02");
  });
});

test("changing display timezone does not rewrite date-only balance values", async () => {
  const updateOriginal = preferencesApi.updateTimezone;
  const createOriginal = balancesApi.createHistory;
  let savedEntry;
  preferencesApi.updateTimezone = async (timezone) => ({ timezone });
  balancesApi.createHistory = async (body) => { savedEntry = body; return body; };
  try {
    await preferencesApi.updateTimezone("America/New_York");
    await balancesApi.createHistory({ entry_date: "2030-11-03", values: {} }, 2);
    assert.equal(savedEntry.entry_date, "2030-11-03");
    assert.equal(typeof savedEntry.entry_date, "string");
  } finally {
    preferencesApi.updateTimezone = updateOriginal;
    balancesApi.createHistory = createOriginal;
  }
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("workspace switching commits data atomically and ignores stale responses", async () => {
  const requests = new Map();
  const states = [];
  const controller = createWorkspaceDataController((workspace) => {
    const request = deferred();
    requests.set(workspace.id, request);
    return request.promise;
  }, (state) => states.push(state));

  const firstSwitch = controller.switchTo({ id: 1, display_name: "Shared" });
  requests.get(1).resolve({ overview: { workspace: 1 }, usage: { workspace: 1 } });
  await firstSwitch;
  const slowSwitch = controller.switchTo({ id: 2, display_name: "Workspace 2" });
  const latestSwitch = controller.switchTo({ id: 3, display_name: "Workspace 3" });
  requests.get(3).resolve({ overview: { workspace: 3 }, usage: { workspace: 3 } });
  assert.equal(await latestSwitch, true);
  requests.get(2).resolve({ overview: { workspace: 2 }, usage: { workspace: 2 } });
  assert.equal(await slowSwitch, false);

  assert.equal(controller.state.workspace.id, 3);
  assert.deepEqual(controller.state.data, { overview: { workspace: 3 }, usage: { workspace: 3 } });
  assert.equal(states.at(-1).workspace.id, 3);
  assert.ok(states.every((state) => !state.data || state.data.overview.workspace === state.data.usage.workspace));
});

test("a failed workspace switch keeps the previous workspace and its matching data", async () => {
  const controller = createWorkspaceDataController(async (workspace) => {
    if (workspace.id === 2) throw new Error("Workspace data is unavailable.");
    return { overview: { workspace: workspace.id }, usage: { workspace: workspace.id } };
  });

  await controller.switchTo({ id: 1, display_name: "Shared" });
  const changed = await controller.switchTo({ id: 2, display_name: "Private" });

  assert.equal(changed, false);
  assert.equal(controller.state.loading, false);
  assert.equal(controller.state.workspace.id, 1);
  assert.deepEqual(controller.state.data, { overview: { workspace: 1 }, usage: { workspace: 1 } });
  assert.match(controller.state.error.message, /unavailable/);
});
