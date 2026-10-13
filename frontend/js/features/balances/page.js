import { balancesApi as api } from "./api.js";
import { usageApi } from "../usage/api.js";
import { workspacesApi } from "../workspaces/api.js";
import { chooseWorkspaceForRole, workspaceContextHtml, workspaceSelectorHtml } from "../workspaces/components/workspaceSelector.js";
import { balanceHistoryTableHtml, addedBalanceHistoryTableHtml } from "./components/history.js";
import { openModal } from "../../shared/components/modal.js";
import { showToast } from "../../shared/components/toast.js";
import { usageRangeSummaryHtml } from "../usage/components/usageRangeSummary.js";
import { providerSymbols } from "./providerUi.js";
import { createWorkspaceDataController } from "./workspaceData.js";
import {
  escapeHtml,
  formatBalance,
  formatDateShort,
  inputNumber,
  localIsoDate,
  numberValue,
  parseNumberInput,
} from "../../shared/utils/format.js";

export function balancePagePermissions(user) {
  const capabilities = new Set(user?.capabilities || []);
  return {
    canWrite: capabilities.has("balances:write"),
    canSelectWorkspace: user?.role === "admin" && capabilities.has("workspaces:manage"),
  };
}

export { chooseWorkspaceForRole, workspaceContextHtml };


// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

function valueMap(entry) {
  return Object.fromEntries((entry?.values || []).map((value) => [value.provider_key, value]));
}

function entryUsedUsd(entry) {
  return (entry?.values || [])
    .filter((value) => value.unit === "USD")
    .reduce((sum, value) => sum + numberValue(value.used_balance), 0);
}

function buildNewBalanceDraft(overview) {
  const latest = valueMap(overview.latest);
  const draft = {};

  for (const provider of overview.providers) {
    const currentLeft = numberValue(latest[provider.provider_key]?.left_balance, 0);
    draft[provider.provider_key] = {
      total: currentLeft,
      used: 0,
      left: currentLeft,
      lastEdited: "used",
    };
  }

  return draft;
}

function buildEditDraft(entry, providers = []) {
  const draft = Object.fromEntries(providers.map((provider) => [provider.provider_key, { total: 0, used: 0, left: 0, lastEdited: "used" }]));
  for (const value of entry.values) {
    draft[value.provider_key] = {
      total: numberValue(value.total_balance),
      used: numberValue(value.used_balance),
      left: numberValue(value.left_balance),
      lastEdited: "used",
    };
  }
  return draft;
}

function buildAddBalanceDraft(overview) {
  const latest = valueMap(overview.latest);
  const draft = {};

  for (const provider of overview.providers) {
    const current = numberValue(latest[provider.provider_key]?.left_balance, 0);
    draft[provider.provider_key] = {
      current,
      add: 0,
      total: current,
    };
  }

  return draft;
}

function draftPayload(draft) {
  return Object.fromEntries(Object.entries(draft).map(([key, row]) => [
    key,
    { total: row.total, used: row.used, left: row.left },
  ]));
}

function additionsPayload(draft) {
  return Object.fromEntries(Object.entries(draft).map(([key, row]) => [key, row.add || 0]));
}

// ---------------------------------------------------------------------------
// Summary and current-balance UI
// ---------------------------------------------------------------------------

function currentCardsHtml(overview) {
  const latest = valueMap(overview.latest);

  return overview.providers.map((provider) => {
    const value = latest[provider.provider_key];
    const left = value?.left_balance ?? 0;
    return `
      <div class="provider-mini">
        <div class="provider-badge">${providerSymbols[provider.provider_key] || provider.display_name.slice(0, 1)}</div>
        <div style="min-width:0">
          <div class="provider-mini-name">${escapeHtml(provider.display_name)}</div>
          <div class="provider-mini-value">${formatBalance(left, provider.unit)}</div>
        </div>
      </div>
    `;
  }).join("");
}

// ---------------------------------------------------------------------------
// New Balance form
// ---------------------------------------------------------------------------

function balanceFormRowsHtml(providers, draft, { totalReadonly = false } = {}) {
  return providers.map((provider) => {
    const row = draft[provider.provider_key];
    return `
      <tr data-balance-row="${provider.provider_key}" data-unit="${provider.unit}">
        <td><strong>${escapeHtml(provider.display_name)}</strong></td>
        <td>
          <input class="input table-input" type="number" min="0" step="any" inputmode="decimal"
            data-field="total" value="${inputNumber(row.total)}" ${totalReadonly ? "readonly" : ""} />
        </td>
        <td>
          <input class="input table-input" type="number" min="0" step="any" inputmode="decimal"
            data-field="used" value="${inputNumber(row.used)}" />
        </td>
        <td class="calc-arrow">⇄</td>
        <td>
          <input class="input table-input" type="number" min="0" step="any" inputmode="decimal"
            data-field="left" value="${inputNumber(row.left)}" />
        </td>
        <td class="unit-cell">${escapeHtml(provider.unit)}</td>
      </tr>
    `;
  }).join("");
}

function usagePanelHtml(providers, draft) {
  const usdTotal = providers
    .filter((provider) => provider.unit === "USD")
    .reduce((sum, provider) => sum + Math.max(0, numberValue(draft[provider.provider_key]?.used)), 0);

  const rows = providers.map((provider) => `
    <div class="total-panel-row">
      <span>${escapeHtml(provider.display_name)}</span>
      <strong>${formatBalance(Math.max(0, numberValue(draft[provider.provider_key]?.used)), provider.unit)}</strong>
    </div>
  `).join("");

  return `
    <div class="total-panel-head">
      <div class="label">Used in this entry (USD)</div>
      <div class="value">${formatBalance(usdTotal, "USD")}</div>
    </div>
    <div class="total-panel-list">${rows}</div>
  `;
}

function isBalanceRowValid(row) {
  if (![row.total, row.used, row.left].every((value) => Number.isFinite(value))) return false;
  if (row.total < 0 || row.used < 0 || row.left < 0) return false;
  return Math.abs((row.used + row.left) - row.total) <= 1e-8;
}

function validateBalanceDraft(providers, draft) {
  for (const provider of providers) {
    const row = draft[provider.provider_key];
    if (!isBalanceRowValid(row)) {
      return `${provider.display_name}: Total, Used and Left must be valid non-negative numbers, and Used + Left must equal Total.`;
    }
  }
  return "";
}

function syncBalanceRow(rowEl, draftRow, field) {
  const totalInput = rowEl.querySelector('[data-field="total"]');
  const usedInput = rowEl.querySelector('[data-field="used"]');
  const leftInput = rowEl.querySelector('[data-field="left"]');
  const activeInput = rowEl.querySelector(`[data-field="${field}"]`);
  const parsed = parseNumberInput(activeInput.value);

  if (parsed === null) {
    draftRow[field] = Number.NaN;
    rowEl.classList.add("row-invalid");
    return;
  }

  draftRow[field] = parsed;

  if (field === "used") {
    draftRow.lastEdited = "used";
    draftRow.left = draftRow.total - draftRow.used;
    leftInput.value = inputNumber(draftRow.left);
  } else if (field === "left") {
    draftRow.lastEdited = "left";
    draftRow.used = draftRow.total - draftRow.left;
    usedInput.value = inputNumber(draftRow.used);
  } else if (field === "total") {
    if (draftRow.lastEdited === "left") {
      draftRow.used = draftRow.total - draftRow.left;
      usedInput.value = inputNumber(draftRow.used);
    } else {
      draftRow.left = draftRow.total - draftRow.used;
      leftInput.value = inputNumber(draftRow.left);
    }
  }

  // IMPORTANT: do not rewrite activeInput.value here. That was the cause of
  // the old cursor-jump bug and the apparent two-decimal input limit.
  rowEl.classList.toggle("row-invalid", !isBalanceRowValid(draftRow));

  if (field !== "total" && totalInput.readOnly) {
    totalInput.value = inputNumber(draftRow.total);
  }
}

function attachBalanceDraftListeners(root, providers, draft, onChange) {
  root.querySelectorAll("[data-balance-row]").forEach((rowEl) => {
    const key = rowEl.dataset.balanceRow;
    const draftRow = draft[key];

    rowEl.querySelectorAll("[data-field]").forEach((input) => {
      if (input.readOnly) return;

      input.addEventListener("input", () => {
        syncBalanceRow(rowEl, draftRow, input.dataset.field);
        onChange?.();
      });

      input.addEventListener("blur", () => {
        const value = parseNumberInput(input.value);
        if (value !== null) input.value = inputNumber(value);
      });
    });
  });
}

function newBalanceSectionHtml(overview, draft, entryDate) {
  return `
    <section class="card section-card editor-section" id="new-balance-section">
      <div class="section-head">
        <div>
          <h2>New Balance Entry</h2>
          <div class="help">Record the new usage or remaining balance for each API key.</div>
        </div>
        <div class="section-actions">
          <button class="btn" type="button" data-reset-new>↻ Reset</button>
          <button class="btn" type="button" data-close-editor>Cancel</button>
          <button class="btn btn-primary" type="button" data-save-history>Save to History</button>
        </div>
      </div>
      <div class="balance-form-wrap">
        <div class="info-strip">
          Enter either <strong>Used</strong> or <strong>Left</strong>. The other field is calculated automatically. You can use more than two decimal places. Total Balance is the latest available balance; use <strong>Add Balance</strong> when you top up an API account. Saving without changing values saves the latest balances again with 0 new usage.
        </div>
        <div class="field entry-date-field">
          <label for="new-entry-date">Date</label>
          <input class="input" id="new-entry-date" type="date" value="${escapeHtml(entryDate)}" />
        </div>
        <div class="balance-form-layout">
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>API Key</th><th>Total Balance</th><th>Used (Input)</th><th></th><th>Left (Input)</th><th>Unit</th></tr>
              </thead>
              <tbody>${balanceFormRowsHtml(overview.providers, draft, { totalReadonly: true })}</tbody>
            </table>
          </div>
          <aside class="total-panel" data-usage-panel>${usagePanelHtml(overview.providers, draft)}</aside>
        </div>
        <div class="error-text" data-save-error></div>
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// Add Balance form
// ---------------------------------------------------------------------------

function addBalanceRowsHtml(providers, draft) {
  return providers.map((provider) => {
    const row = draft[provider.provider_key];
    return `
      <tr data-add-row="${provider.provider_key}">
        <td><strong>${escapeHtml(provider.display_name)}</strong></td>
        <td>${formatBalance(row.current, provider.unit)}</td>
        <td>
          <input class="input table-input" type="number" min="0" step="any" inputmode="decimal"
            data-add-input placeholder="0" value="" />
        </td>
        <td class="calc-arrow">＋</td>
        <td data-add-total><strong>${formatBalance(row.total, provider.unit)}</strong></td>
        <td class="unit-cell">${escapeHtml(provider.unit)}</td>
      </tr>
    `;
  }).join("");
}

function addBalanceSummaryHtml(providers, draft) {
  const groups = new Map();
  for (const provider of providers) {
    const amount = Math.max(0, numberValue(draft[provider.provider_key]?.add));
    groups.set(provider.unit, (groups.get(provider.unit) || 0) + amount);
  }

  const byProvider = providers.map((provider) => `
    <div class="total-panel-row">
      <span>${escapeHtml(provider.display_name)}</span>
      <strong>${formatBalance(Math.max(0, numberValue(draft[provider.provider_key]?.add)), provider.unit)}</strong>
    </div>
  `).join("");

  const totals = [...groups.entries()].map(([unit, value]) => `${formatBalance(value, unit)}`).join(" • ");

  return `
    <div class="total-panel-head">
      <div class="label">Balance being added</div>
      <div class="add-summary-units">${totals}</div>
    </div>
    <div class="total-panel-list">${byProvider}</div>
  `;
}

function attachAddBalanceListeners(root, providers, draft, onChange) {
  const providerMap = Object.fromEntries(providers.map((provider) => [provider.provider_key, provider]));

  root.querySelectorAll("[data-add-row]").forEach((rowEl) => {
    const key = rowEl.dataset.addRow;
    const provider = providerMap[key];
    const input = rowEl.querySelector("[data-add-input]");
    const totalEl = rowEl.querySelector("[data-add-total]");

    input.addEventListener("input", () => {
      const parsed = parseNumberInput(input.value);
      const amount = parsed === null ? 0 : parsed;
      draft[key].add = amount;
      draft[key].total = draft[key].current + amount;
      rowEl.classList.toggle("row-invalid", amount < 0);
      totalEl.innerHTML = `<strong>${formatBalance(draft[key].total, provider.unit)}</strong>`;
      onChange?.();
    });

    input.addEventListener("blur", () => {
      const parsed = parseNumberInput(input.value);
      if (parsed !== null) input.value = inputNumber(parsed);
    });
  });
}

function addBalanceSectionHtml(overview, draft, entryDate) {
  return `
    <section class="card section-card editor-section" id="add-balance-section">
      <div class="section-head">
        <div>
          <h2>Add Balance</h2>
          <div class="help">Use this when you buy or top up API credits/funds.</div>
        </div>
        <div class="section-actions">
          <button class="btn" type="button" data-close-editor>Cancel</button>
          <button class="btn btn-primary" type="button" data-save-added-balance>Save Added Balance</button>
        </div>
      </div>
      <div class="balance-form-wrap">
        <div class="info-strip">
          Type only the amount you added. <strong>New Total Balance = Current Balance + Added Balance</strong>. Added funds are saved as a new history snapshot and are not counted as usage.
        </div>
        <div class="field entry-date-field">
          <label for="add-entry-date">Date</label>
          <input class="input" id="add-entry-date" type="date" value="${escapeHtml(entryDate)}" />
        </div>
        <div class="balance-form-layout">
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>API Key</th><th>Current Balance</th><th>Add Balance (Input)</th><th></th><th>New Total Balance</th><th>Unit</th></tr>
              </thead>
              <tbody>${addBalanceRowsHtml(overview.providers, draft)}</tbody>
            </table>
          </div>
          <aside class="total-panel" data-add-summary>${addBalanceSummaryHtml(overview.providers, draft)}</aside>
        </div>
        <div class="error-text" data-add-error></div>
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// Edit / Delete saved history
// ---------------------------------------------------------------------------

async function showEditModal(entryId, overview, refreshPage, workspaceId, isCurrentWorkspace = () => true) {
  let entry;
  try {
    entry = await api.getHistoryEntry(entryId, workspaceId);
    if (!isCurrentWorkspace()) return;
  } catch (error) {
    if (isCurrentWorkspace()) showToast(error.message, "error");
    return;
  }

  const draft = buildEditDraft(entry, overview.providers);
  const bodyHtml = `
    <div class="edit-form-grid">
      <div class="field edit-date-row">
        <label for="edit-entry-date">History date</label>
        <input id="edit-entry-date" class="input" type="date" value="${escapeHtml(entry.entry_date)}" />
      </div>
      <div class="info-strip">
        Correct any saved value here. Used and Left recalculate each other, and values may contain more than two decimal places.
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>API Key</th><th>Total Balance</th><th>Used</th><th></th><th>Left</th><th>Unit</th></tr>
          </thead>
          <tbody>${balanceFormRowsHtml(overview.providers, draft)}</tbody>
        </table>
      </div>
      <div class="error-text" data-edit-error></div>
    </div>
  `;

  const footerHtml = `
    <button class="btn" type="button" data-modal-close>Cancel</button>
    <button class="btn btn-primary" type="button" data-save-edit>Save changes</button>
  `;

  openModal({
    title: `Edit saved balances — ${formatDateShort(entry.entry_date)}`,
    bodyHtml,
    footerHtml,
    onReady: ({ root, close }) => {
      attachBalanceDraftListeners(root, overview.providers, draft);
      const saveButton = root.querySelector("[data-save-edit]");
      const errorEl = root.querySelector("[data-edit-error]");

      saveButton.addEventListener("click", async () => {
        if (!isCurrentWorkspace()) { errorEl.textContent = "Workspace changed. Close this editor and reopen the entry."; return; }
        const validationError = validateBalanceDraft(overview.providers, draft);
        if (validationError) {
          errorEl.textContent = validationError;
          return;
        }

        saveButton.disabled = true;
        errorEl.textContent = "";
        try {
          const entryDate = root.querySelector("#edit-entry-date").value;
          await api.updateHistory(entryId, {
            entry_date: entryDate,
            values: draftPayload(draft),
          }, workspaceId);
          close();
          showToast("Saved history entry updated.", "success");
          if (isCurrentWorkspace()) await refreshPage({ resetDrafts: true });
        } catch (error) {
          errorEl.textContent = error.message;
        } finally {
          saveButton.disabled = false;
        }
      });
    },
  });
}

async function showTopupModal(entryId, refreshPage, workspaceId, isCurrentWorkspace, classify = false) {
  let entry;
  try {
    entry = await api.getHistoryEntry(entryId, workspaceId);
    if (!isCurrentWorkspace()) return;
  } catch (error) { if (isCurrentWorkspace()) showToast(error.message, "error"); return; }
  const rows = entry.values.map((value) => `<tr data-topup-edit-row="${escapeHtml(value.provider_key)}">
    <td><strong>${escapeHtml(value.display_name)}</strong></td>
    <td data-topup-before>${classify ? "Enter actual addition" : formatBalance(value.balance_before, value.unit)}</td>
    <td><input aria-label="${escapeHtml(value.display_name)} amount added" class="input table-input" type="number" min="0" step="any"
      data-topup-amount value="${classify ? "" : inputNumber(value.added_balance)}" /></td>
    <td data-topup-after>${formatBalance(value.left_balance, value.unit)}</td>
    <td>${escapeHtml(value.unit)}</td></tr>`).join("");
  openModal({
    title: classify ? "Classify legacy entry as a top-up" : "Edit added balance",
    bodyHtml: `<div class="edit-form-grid"><div class="field edit-date-row"><label for="topup-edit-date">Date</label>
      <input class="input" id="topup-edit-date" type="date" value="${escapeHtml(entry.entry_date)}" /></div>
      <div class="info-strip">${classify ? "Supply the actual amounts added. Saved balances stay unchanged; previous balances are calculated from those amounts. Every provider must have zero usage." : "Correct the amount added. The recorded balance before stays fixed and the balance after is recalculated."}</div>
      <div class="table-wrap"><table><thead><tr><th>API provider</th><th>Balance before</th><th>Amount added</th><th>Balance after</th><th>Unit</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="error-text" data-topup-edit-error></div></div>`,
    footerHtml: '<button class="btn" type="button" data-modal-close>Cancel</button><button class="btn btn-primary" type="button" data-save-topup>Save changes</button>',
    onReady: ({ root, close }) => {
      const errorEl = root.querySelector("[data-topup-edit-error]");
      const rowEls = [...root.querySelectorAll("[data-topup-edit-row]")];
      const valueByKey = valueMap(entry);
      rowEls.forEach((row) => row.querySelector("[data-topup-amount]").addEventListener("input", () => {
        const value = valueByKey[row.dataset.topupEditRow];
        const amount = parseNumberInput(row.querySelector("[data-topup-amount]").value);
        if (amount === null || amount < 0) return;
        row.querySelector("[data-topup-before]").textContent = formatBalance(classify ? value.left_balance - amount : value.balance_before, value.unit);
        row.querySelector("[data-topup-after]").textContent = formatBalance(classify ? value.left_balance : value.balance_before + amount, value.unit);
        errorEl.textContent = "";
      }));
      const button = root.querySelector("[data-save-topup]");
      button.addEventListener("click", async () => {
        if (!isCurrentWorkspace()) { errorEl.textContent = "Workspace changed. Close this editor and reopen the entry."; return; }
        const additions = {};
        for (const row of rowEls) {
          const input = row.querySelector("[data-topup-amount]");
          const amount = input.value.trim() === "" ? 0 : parseNumberInput(input.value);
          if (amount === null || amount < 0) { errorEl.textContent = "Amounts must be valid non-negative numbers."; return; }
          additions[row.dataset.topupEditRow] = amount;
        }
        if (!Object.values(additions).some((amount) => amount > 0)) { errorEl.textContent = "Enter a positive addition for at least one provider."; return; }
        button.disabled = true;
        errorEl.textContent = "";
        try {
          await api.updateAddedBalance(entryId, { entry_date: root.querySelector("#topup-edit-date").value, additions }, workspaceId);
          close();
          if (isCurrentWorkspace()) await refreshPage({resetDrafts:true});
          showToast(classify ? "Legacy entry classified as an added balance." : "Added balance updated.", "success");
        } catch (error) { errorEl.textContent = error.message; }
        finally { button.disabled = false; }
      });
    },
  });
}

function showDeleteModal(entryId, entryDate, refreshPage, workspaceId, isCurrentWorkspace = () => true) {
  const bodyHtml = `
    <div class="delete-warning">
      <strong>Delete the saved entry for ${formatDateShort(entryDate)}?</strong>
      <p>This removes the history row and its usage from the totals. This action cannot be undone.</p>
    </div>
  `;

  const footerHtml = `
    <button class="btn" type="button" data-modal-close>Cancel</button>
    <button class="btn btn-danger" type="button" data-confirm-delete>Delete entry</button>
  `;

  openModal({
    title: "Delete balance history entry",
    bodyHtml,
    footerHtml,
    onReady: ({ root, close }) => {
      const button = root.querySelector("[data-confirm-delete]");
      button.addEventListener("click", async () => {
        if (!isCurrentWorkspace()) { showToast("Workspace changed. Close this dialog and reopen the entry.", "error"); return; }
        button.disabled = true;
        try {
          await api.deleteHistory(entryId, workspaceId);
          close();
          showToast("Balance history entry deleted.", "success");
          if (isCurrentWorkspace()) await refreshPage({ resetDrafts: true });
        } catch (error) {
          showToast(error.message, "error");
          button.disabled = false;
        }
      });
    },
  });
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export async function renderApiBalancesPage(container, { onUnauthorized, user } = {}) {
  container.innerHTML = `<div class="loading-row">Loading API key balances…</div>`;

  const permissions = balancePagePermissions(user);
  let workspaces = [];
  let activeWorkspace = null;
  let workspaceId = null;
  let overview;
  let historyPage = 1;
  let pageSize = 5;
  let topupPage = 1;
  let topupPageSize = 5;
  let activeEditor = null; // null | "new" | "add"
  let newDraft = null;
  let addDraft = null;
  let newEntryDate = localIsoDate();
  let addEntryDate = localIsoDate();

  // Usage-range state is separate from Balance History pagination so users can
  // inspect 1 day / 1 week / 1 month / custom ranges independently.
  let usageSummary = null;
  let usagePeriod = "all";
  let usageLoading = false;
  let usageError = "";
  let showCustomRange = false;
  let customUsageStart = "";
  let customUsageEnd = "";
  let workspaceLoading = false;
  let renderWorkspacePage = null;
  let refreshRequestNumber = 0;
  let usageRequestNumber = 0;
  let workspaceGeneration = 0;
  const workspaceGuard = () => {
    const target = workspaceId;
    const generation = workspaceGeneration;
    return () => !workspaceLoading && Number(workspaceId) === Number(target) && generation === workspaceGeneration;
  };

  const requestedWorkspaceId = () => {
    const query = globalThis.window?.location?.hash?.split("?")[1] || "";
    const value = new URLSearchParams(query).get("workspace_id");
    return value && Number.isInteger(Number(value)) ? Number(value) : null;
  };

  const fetchOverview = (targetWorkspaceId, page = historyPage, size = pageSize, additionsPage = topupPage) =>
    api.getOverview(page, size, targetWorkspaceId, additionsPage, topupPageSize);

  const fetchUsageSummary = (targetWorkspaceId) => usageApi.getSummary({
    period: usagePeriod,
    startDate: usagePeriod === "custom" ? customUsageStart : "",
    endDate: usagePeriod === "custom" ? customUsageEnd : "",
    workspaceId: targetWorkspaceId,
  });

  const applyUsageSummary = (nextSummary) => {
    usageSummary = nextSummary;
    // Give the custom calendar useful defaults the first time it is opened.
    if (!customUsageStart && usageSummary?.start_date) customUsageStart = usageSummary.start_date;
    if (!customUsageEnd && usageSummary?.end_date) customUsageEnd = usageSummary.end_date;
  };

  const workspaceDataController = createWorkspaceDataController(async (workspace) => {
    const [nextOverview, nextUsageSummary] = await Promise.all([
      fetchOverview(workspace.id, 1, pageSize, 1),
      fetchUsageSummary(workspace.id),
    ]);
    return { overview: nextOverview, usageSummary: nextUsageSummary };
  }, (state) => {
    workspaceLoading = state.loading;
    if (state.workspace && state.data) {
      const previousWorkspaceId = workspaceId;
      activeWorkspace = state.workspace;
      workspaceId = state.workspace.id;
      overview = state.data.overview;
      historyPage = overview.pagination?.page || 1;
      pageSize = overview.pagination?.page_size || pageSize;
      topupPage = overview.topup_pagination?.page || 1;
      topupPageSize = overview.topup_pagination?.page_size || topupPageSize;
      applyUsageSummary(state.data.usageSummary);
      if (previousWorkspaceId != null && Number(previousWorkspaceId) !== Number(workspaceId)) {
        newDraft = buildNewBalanceDraft(overview);
        addDraft = buildAddBalanceDraft(overview);
        activeEditor = null;
        newEntryDate = localIsoDate();
        addEntryDate = localIsoDate();
      }
    }
    renderWorkspacePage?.();
  });

  try {
    const workspaceResult = await workspacesApi.getWorkspaces();
    workspaces = workspaceResult.workspaces || [];
    activeWorkspace = chooseWorkspaceForRole(user, workspaces, requestedWorkspaceId());
    if (!activeWorkspace) throw new Error("No workspace is available for this account.");
    const loaded = await workspaceDataController.switchTo(activeWorkspace);
    if (!loaded) throw workspaceDataController.state.error || new Error("Could not load this workspace.");
  } catch (error) {
    if (error.status === 401) {
      onUnauthorized?.();
      return;
    }
    container.innerHTML = `<div class="card empty-state">${escapeHtml(error.message)}</div>`;
    return;
  }

  const refreshPage = async ({ resetDrafts = false } = {}) => {
    const thisRequest = ++refreshRequestNumber;
    const requestedWorkspaceId = workspaceId;
    try {
      const [nextOverview, nextUsageSummary] = await Promise.all([
        fetchOverview(requestedWorkspaceId),
        fetchUsageSummary(requestedWorkspaceId),
      ]);
      if (thisRequest !== refreshRequestNumber
        || Number(requestedWorkspaceId) !== Number(workspaceId)
        || workspaceLoading) return;
      overview = nextOverview;
      historyPage = overview.pagination?.page || historyPage;
      pageSize = overview.pagination?.page_size || pageSize;
      topupPage = overview.topup_pagination?.page || 1;
      topupPageSize = overview.topup_pagination?.page_size || topupPageSize;
      applyUsageSummary(nextUsageSummary);
      if (resetDrafts) {
        newDraft = buildNewBalanceDraft(overview);
        addDraft = buildAddBalanceDraft(overview);
        activeEditor = null;
        newEntryDate = localIsoDate();
        addEntryDate = localIsoDate();
      }
      render();
    } catch (error) {
      if (thisRequest !== refreshRequestNumber) return;
      if (error.status === 401) onUnauthorized?.();
      else showToast(error.message, "error");
    }
  };

  const render = () => {
    const usdTotal = numberValue(overview.summary?.by_unit?.USD, 0);
    const creditsTotal = numberValue(overview.summary?.by_unit?.credits, 0);
    const chutesTotal = numberValue(overview.summary?.by_unit?.t, 0);
    const latestDate = overview.latest?.entry_date || "—";

    const editorHtml = !permissions.canWrite ? "" : activeEditor === "new"
      ? newBalanceSectionHtml(overview, newDraft, newEntryDate)
      : activeEditor === "add"
        ? addBalanceSectionHtml(overview, addDraft, addEntryDate)
        : "";
    const workspaceSelector = permissions.canSelectWorkspace
      ? workspaceSelectorHtml({ role: user.role, workspaces, selectedWorkspaceId: workspaceId })
      : "";
    const workspaceContext = permissions.canSelectWorkspace ? "" : workspaceContextHtml(activeWorkspace);

    container.innerHTML = `
      <div class="page-heading">
        <div>
          <h1>API keys balances</h1>
          ${workspaceContext}
        </div>
        <div class="page-heading-actions">
          ${workspaceSelector}
          ${workspaceLoading ? '<span class="help" role="status">Loading workspace…</span>' : ""}
          ${permissions.canWrite ? `
            <button class="btn btn-soft" type="button" data-open-add>＋ Add Balance</button>
            <button class="btn btn-primary" type="button" data-open-new>＋ New Balance</button>
          ` : ""}
        </div>
      </div>

      <div class="summary-grid">
        <section class="card used-summary">
          <div class="summary-icon">▥</div>
          <div>
            <div class="summary-label">TOTAL USED BALANCE (USD)</div>
            <div class="summary-value">${formatBalance(usdTotal, "USD")}</div>
          </div>
          <div class="summary-note">
            Cumulative USD usage across all saved history.<br />Credits used: ${formatBalance(creditsTotal, "credits")} • Chutes used: ${formatBalance(chutesTotal, "t")}<br />Latest entry: ${formatDateShort(latestDate)}
          </div>
        </section>

        <section class="card current-card">
          <div class="current-card-head">
            <h2>Current API Key Balances <span class="help">(Latest: ${formatDateShort(latestDate)})</span></h2>
          </div>
          <div class="provider-cards">${currentCardsHtml(overview)}</div>
        </section>
      </div>

      ${usageRangeSummaryHtml({
        summary: usageSummary,
        activePeriod: usagePeriod,
        showCustomRange,
        customStart: customUsageStart,
        customEnd: customUsageEnd,
        loading: usageLoading,
        error: usageError,
      })}

      ${editorHtml}

      <section class="card section-card" id="balance-history-section">
        <div class="section-head">
          <div>
            <h2>Balance History</h2>
            <div class="help">${permissions.canWrite ? "Edit a saved row if a value was wrong, or delete a row you do not want to keep." : "Balance history is read-only for this account."}</div>
          </div>
          <div class="help">${overview.pagination?.total_items || 0} entries • ${overview.providers.length} providers</div>
        </div>
        <div class="section-body">${balanceHistoryTableHtml(overview, permissions)}</div>
      </section>
      <section class="card section-card" id="added-balance-history-section">
        <div class="section-head"><div>
          <h2>Added Balance History</h2>
          <div class="help">Recorded additions, with each provider's balance before and after. Additions count as zero usage.</div>
        </div><div class="help">${overview.topup_pagination?.total_items || 0} entries</div></div>
        <div class="section-body">${addedBalanceHistoryTableHtml(overview, permissions)}</div>
      </section>
    `;

    if (workspaceLoading) {
      container.querySelectorAll("button, input, select, textarea").forEach((control) => {
        control.disabled = true;
      });
    }

    container.querySelector("[data-workspace-select]")?.addEventListener("change", async (event) => {
      const nextWorkspace = chooseWorkspaceForRole(user, workspaces, Number(event.target.value));
      if (workspaceLoading || !nextWorkspace || Number(nextWorkspace.id) === Number(workspaceId)) return;
      workspaceGeneration += 1;
      refreshRequestNumber += 1;
      usageRequestNumber += 1;
      usageLoading = false;
      const loaded = await workspaceDataController.switchTo(nextWorkspace);
      if (!loaded && workspaceDataController.state.error) showToast(workspaceDataController.state.error.message, "error");
    });

    // Usage range controls. Preset ranges end on the latest saved history date.
    const selectUsagePeriod = async (period) => {
      usagePeriod = period;
      showCustomRange = false;
      usageLoading = true;
      usageError = "";
      const thisRequest = ++usageRequestNumber;
      const requestedWorkspaceId = workspaceId;
      render();

      try {
        const nextSummary = await fetchUsageSummary(requestedWorkspaceId);
        if (thisRequest !== usageRequestNumber || Number(requestedWorkspaceId) !== Number(workspaceId) || workspaceLoading) return;
        applyUsageSummary(nextSummary);
      } catch (error) {
        if (thisRequest !== usageRequestNumber) return;
        if (error.status === 401) {
          onUnauthorized?.();
          return;
        }
        usageError = error.message;
      } finally {
        if (thisRequest === usageRequestNumber) {
          usageLoading = false;
          render();
        }
      }
    };

    container.querySelectorAll("[data-usage-period]").forEach((button) => {
      button.addEventListener("click", () => selectUsagePeriod(button.dataset.usagePeriod));
    });

    container.querySelector("[data-open-custom-range]")?.addEventListener("click", () => {
      if (!customUsageStart) customUsageStart = usageSummary?.start_date || localIsoDate();
      if (!customUsageEnd) customUsageEnd = usageSummary?.end_date || localIsoDate();
      showCustomRange = true;
      usageError = "";
      render();
    });

    container.querySelector("[data-usage-start]")?.addEventListener("change", (event) => {
      customUsageStart = event.target.value;
      usageError = "";
    });

    container.querySelector("[data-usage-end]")?.addEventListener("change", (event) => {
      customUsageEnd = event.target.value;
      usageError = "";
    });

    container.querySelector("[data-close-custom-range]")?.addEventListener("click", () => {
      showCustomRange = false;
      usageError = "";
      render();
    });

    container.querySelector("[data-apply-custom-range]")?.addEventListener("click", async () => {
      if (!customUsageStart || !customUsageEnd) {
        usageError = "Choose both From and To dates.";
        render();
        return;
      }
      if (customUsageStart > customUsageEnd) {
        usageError = "From date cannot be after To date.";
        render();
        return;
      }

      usagePeriod = "custom";
      usageLoading = true;
      usageError = "";
      const thisRequest = ++usageRequestNumber;
      const requestedWorkspaceId = workspaceId;
      render();

      try {
        const nextSummary = await fetchUsageSummary(requestedWorkspaceId);
        if (thisRequest !== usageRequestNumber || Number(requestedWorkspaceId) !== Number(workspaceId) || workspaceLoading) return;
        applyUsageSummary(nextSummary);
        showCustomRange = true;
      } catch (error) {
        if (thisRequest !== usageRequestNumber) return;
        if (error.status === 401) {
          onUnauthorized?.();
          return;
        }
        usageError = error.message;
      } finally {
        if (thisRequest === usageRequestNumber) {
          usageLoading = false;
          render();
        }
      }
    });

    // Top actions: editor sections are not rendered until the user asks for them.
    container.querySelector("[data-open-new]")?.addEventListener("click", () => {
      newDraft = buildNewBalanceDraft(overview);
      newEntryDate = localIsoDate();
      activeEditor = "new";
      render();
      document.getElementById("new-balance-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    container.querySelector("[data-open-add]")?.addEventListener("click", () => {
      addDraft = buildAddBalanceDraft(overview);
      addEntryDate = localIsoDate();
      activeEditor = "add";
      render();
      document.getElementById("add-balance-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    container.querySelectorAll("[data-close-editor]").forEach((button) => {
      button.addEventListener("click", () => {
        activeEditor = null;
        render();
      });
    });

    // New Balance editor.
    if (activeEditor === "new") {
      const usagePanel = container.querySelector("[data-usage-panel]");
      const errorEl = container.querySelector("[data-save-error]");
      const dateInput = container.querySelector("#new-entry-date");

      dateInput.addEventListener("change", () => { newEntryDate = dateInput.value; });

      attachBalanceDraftListeners(container, overview.providers, newDraft, () => {
        usagePanel.innerHTML = usagePanelHtml(overview.providers, newDraft);
        errorEl.textContent = "";
      });

      container.querySelector("[data-reset-new]").addEventListener("click", () => {
        newDraft = buildNewBalanceDraft(overview);
        newEntryDate = localIsoDate();
        render();
        document.getElementById("new-balance-section")?.scrollIntoView({ block: "start" });
      });

      container.querySelector("[data-save-history]").addEventListener("click", async (event) => {
        const validationError = validateBalanceDraft(overview.providers, newDraft);
        if (validationError) {
          errorEl.textContent = validationError;
          return;
        }

        const button = event.currentTarget;
        button.disabled = true;
        errorEl.textContent = "";
        try {
          await api.createHistory({
            expected_latest_entry_id: overview.latest?.id ?? null,
            entry_date: newEntryDate,
            values: draftPayload(newDraft),
          }, workspaceId);
          showToast("Balance entry saved to history.", "success");
          historyPage = 1;
          await refreshPage({ resetDrafts: true });
        } catch (error) {
          if (error.status === 401) {
            onUnauthorized?.();
            return;
          }
          errorEl.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      });
    }

    // Add Balance editor.
    if (activeEditor === "add") {
      const summary = container.querySelector("[data-add-summary]");
      const errorEl = container.querySelector("[data-add-error]");
      const dateInput = container.querySelector("#add-entry-date");

      dateInput.addEventListener("change", () => { addEntryDate = dateInput.value; });

      attachAddBalanceListeners(container, overview.providers, addDraft, () => {
        summary.innerHTML = addBalanceSummaryHtml(overview.providers, addDraft);
        errorEl.textContent = "";
      });

      container.querySelector("[data-save-added-balance]").addEventListener("click", async (event) => {
        const hasPositiveAmount = Object.values(addDraft).some((row) => numberValue(row.add) > 0);
        if (!hasPositiveAmount) {
          errorEl.textContent = "Enter an amount greater than 0 for at least one API key.";
          return;
        }

        const hasNegativeAmount = Object.values(addDraft).some((row) => numberValue(row.add) < 0);
        if (hasNegativeAmount) {
          errorEl.textContent = "Added balance cannot be negative.";
          return;
        }

        const button = event.currentTarget;
        button.disabled = true;
        errorEl.textContent = "";
        try {
          await api.addBalances({
            entry_date: addEntryDate,
            additions: additionsPayload(addDraft),
          }, workspaceId);
          showToast("Added balance saved. Current totals were updated.", "success");
          topupPage = 1;
          await refreshPage({ resetDrafts: true });
        } catch (error) {
          if (error.status === 401) {
            onUnauthorized?.();
            return;
          }
          errorEl.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      });
    }

    // Entry-kind-specific correction and explicit legacy classification.
    container.querySelectorAll("[data-edit-topup], [data-classify-entry]").forEach((button) => {
      button.addEventListener("click", () => showTopupModal(Number(button.dataset.editTopup || button.dataset.classifyEntry),
        refreshPage, workspaceId, workspaceGuard(), Boolean(button.dataset.classifyEntry)));
    });

    // History edit/delete actions.
    container.querySelectorAll("[data-edit-entry]").forEach((button) => {
      button.addEventListener("click", () => showEditModal(Number(button.dataset.editEntry), overview, refreshPage, workspaceId, workspaceGuard()));
    });

    container.querySelectorAll("[data-delete-entry]").forEach((button) => {
      button.addEventListener("click", () => {
        showDeleteModal(Number(button.dataset.deleteEntry), button.dataset.entryDate, refreshPage, workspaceId, workspaceGuard());
      });
    });

    // Pagination.
    container.querySelectorAll("[data-history-page]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        historyPage = Number(button.dataset.historyPage) || 1;
        await refreshPage();
        container.querySelector("#balance-history-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    container.querySelectorAll("[data-topup-page]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        topupPage = Number(button.dataset.topupPage) || 1;
        await refreshPage();
        container.querySelector("#added-balance-history-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    container.querySelector("[data-topup-page-size]")?.addEventListener("change", async (event) => {
      topupPageSize = Number(event.target.value) || 5;
      topupPage = 1;
      await refreshPage();
    });

    container.querySelector("[data-history-page-size]")?.addEventListener("change", async (event) => {
      pageSize = Number(event.target.value) || 5;
      historyPage = 1;
      await refreshPage();
    });
  };

  renderWorkspacePage = render;
  newDraft = buildNewBalanceDraft(overview);
  addDraft = buildAddBalanceDraft(overview);
  render();
}
