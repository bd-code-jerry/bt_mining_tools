import test from "node:test";
import assert from "node:assert/strict";

import { preferencesApi } from "../frontend/js/features/preferences/api.js";
import { renderTimezoneSelector } from "../frontend/js/shared/components/timezoneSelector.js";

function fakeContainer() {
  let html = "";
  let listener;
  const select = {
    value: "UTC",
    addEventListener(type, handler) { if (type === "change") listener = handler; },
  };
  const error = { textContent: "" };
  return {
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; },
    querySelector(selector) {
      if (selector === "[data-timezone-select]") return select;
      if (selector === "[data-timezone-error]") return error;
      return null;
    },
    select,
    error,
    async change(value) { select.value = value; await listener({ target: select }); },
  };
}

test("all signed-in roles get UTC and Eastern Time choices with their saved value selected", () => {
  for (const role of ["admin", "member", "user"]) {
    const container = fakeContainer();
    renderTimezoneSelector(container, { timezone: "America/New_York", role });
    assert.match(container.innerHTML, /UTC/);
    assert.match(container.innerHTML, /Eastern Time \(ET\)/);
    assert.match(container.innerHTML, /value="America\/New_York" selected/);
  }
});

test("timezone changes save the account preference and notify the signed-in shell", async () => {
  const original = preferencesApi.updateTimezone;
  let saved;
  let updated;
  preferencesApi.updateTimezone = async (timezone) => { saved = timezone; return { timezone }; };
  try {
    const container = fakeContainer();
    renderTimezoneSelector(container, {
      timezone: "UTC",
      role: "member",
      onUpdated(value) { updated = value; },
    });
    await container.change("America/New_York");
    assert.equal(saved, "America/New_York");
    assert.equal(updated, "America/New_York");
  } finally {
    preferencesApi.updateTimezone = original;
  }
});

test("timezone selection waits for the active page to refresh its timezone-dependent data", async () => {
  let releaseRefresh;
  let startedRefresh;
  const started = new Promise((resolve) => { startedRefresh = resolve; });
  const container = fakeContainer();
  renderTimezoneSelector(container, {
    timezone: "UTC",
    async savePreference(timezone) { return { timezone }; },
    onUpdated() {
      startedRefresh();
      return new Promise((resolve) => { releaseRefresh = resolve; });
    },
  });

  const change = container.change("America/New_York");
  await started;
  assert.equal(container.select.disabled, true);
  releaseRefresh();
  await change;
  assert.equal(container.select.disabled, false);
});

test("a failed timezone update reverts to the latest saved choice", async () => {
  let calls = 0;
  const container = fakeContainer();
  renderTimezoneSelector(container, {
    timezone: "America/New_York",
    async savePreference(timezone) {
      calls += 1;
      if (calls === 1) return { timezone };
      throw new Error("Could not save time zone.");
    },
  });
  await container.change("UTC");
  await container.change("America/New_York");
  assert.equal(container.select.value, "UTC");
  assert.match(container.error.textContent, /could not save/i);
});
