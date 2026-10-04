import test from "node:test";
import assert from "node:assert/strict";

import { totalBalancesApi } from "../frontend/js/features/total-balances/api.js";
import { renderTotalBalancePage } from "../frontend/js/features/total-balances/page.js";

test("Total Balance page uses only the aggregate endpoint and renders unit-separated rows", async () => {
  const original = totalBalancesApi.getSummary;
  let calls = 0;
  totalBalancesApi.getSummary = async () => {
    calls += 1;
    return {
      workspaces: [
        {
          workspace_id: 2,
          workspace_kind: "private",
          label: "<img src=x onerror=alert(1)>",
          values: [
            { provider_key: "openrouter", display_name: "OpenRouter", unit: "USD", total_balance: 10, left_balance: 8, total_spent: 2 },
            { provider_key: "firecrawl", display_name: "Firecrawl", unit: "credits", total_balance: 50, left_balance: 45, total_spent: 5 },
          ],
        },
      ],
      team_totals: [
        { provider_key: "openrouter", display_name: "OpenRouter", unit: "USD", total_balance: 10, left_balance: 8, total_spent: 2 },
        { provider_key: "firecrawl", display_name: "Firecrawl", unit: "credits", total_balance: 50, left_balance: 45, total_spent: 5 },
      ],
    };
  };
  let html = "";
  const container = { set innerHTML(value) { html = value; }, get innerHTML() { return html; } };
  try {
    await renderTotalBalancePage(container, {});
    assert.equal(calls, 1);
    assert.match(html, /Total Balance/);
    assert.match(html, /10\.00/);
    assert.match(html, /50 credits/);
    assert.match(html, /Workspace totals/);
    assert.doesNotMatch(html, /<img src=x/);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /entry_date|history_id|data-edit/);
  } finally {
    totalBalancesApi.getSummary = original;
  }
});

test("an unauthorized aggregate request invokes the protected-route handler", async () => {
  const original = totalBalancesApi.getSummary;
  let unauthorized = false;
  totalBalancesApi.getSummary = async () => {
    const error = new Error("Not signed in.");
    error.status = 401;
    throw error;
  };
  let html = "";
  const container = { set innerHTML(value) { html = value; }, get innerHTML() { return html; } };
  try {
    await renderTotalBalancePage(container, { onUnauthorized() { unauthorized = true; } });
    assert.equal(unauthorized, true);
  } finally {
    totalBalancesApi.getSummary = original;
  }
});

test("Total Balance API requests only the aggregate summary route", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    return {
      ok: true,
      headers: { get: () => "application/json" },
      async json() { return { workspaces: [], team_totals: [] }; },
    };
  };
  try {
    await totalBalancesApi.getSummary();
    assert.deepEqual(calls, ["/api/total-balances/summary"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
