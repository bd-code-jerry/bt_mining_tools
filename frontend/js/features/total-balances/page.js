import { totalBalancesApi } from "./api.js";
import { escapeHtml, formatBalance } from "../../shared/utils/format.js";

function valueForDisplay(amount, unit) {
  const formatted = formatBalance(amount, unit);
  return unit === "USD" || unit === "t" ? formatted : `${formatted} ${escapeHtml(unit)}`;
}

function valuesTable(values) {
  if (!values.length) return `<div class="total-balance-empty">No balance entries yet.</div>`;
  return `
    <div class="table-wrap">
      <table class="total-balance-table">
        <thead><tr><th>Provider</th><th>Total balance</th><th>Left balance</th><th>Total spent</th><th>Unit</th></tr></thead>
        <tbody>${values.map((value) => `
          <tr>
            <td><strong>${escapeHtml(value.display_name)}</strong></td>
            <td>${valueForDisplay(value.total_balance, value.unit)}</td>
            <td>${valueForDisplay(value.left_balance, value.unit)}</td>
            <td>${valueForDisplay(value.total_spent, value.unit)}</td>
            <td>${escapeHtml(value.unit)}</td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>
  `;
}

export function totalBalancePageHtml(summary) {
  const workspaceSections = (summary.workspaces || []).map((workspace) => `
    <section class="card total-balance-workspace" data-workspace-row="${Number(workspace.workspace_id)}">
      <div class="total-balance-section-head">
        <div>
          <div class="total-balance-kind">${workspace.workspace_kind === "shared" ? "Shared workspace" : "Private workspace"}</div>
          <h2>${escapeHtml(workspace.label)}</h2>
        </div>
      </div>
      ${valuesTable(workspace.values || [])}
    </section>
  `).join("");
  return `
    <div class="page-heading"><div><h1>Total Balance</h1><p class="page-subtitle">Latest balances and cumulative spend across all workspaces.</p></div></div>
    <section class="card total-balance-workspace team-total-card">
      <div class="total-balance-section-head"><div><div class="total-balance-kind">Combined view</div><h2>Workspace totals</h2></div></div>
      ${valuesTable(summary.team_totals || [])}
    </section>
    <div class="total-balance-workspaces">${workspaceSections || `<div class="card total-balance-empty">No workspaces are available.</div>`}</div>
  `;
}

export async function renderTotalBalancePage(container, { onUnauthorized } = {}) {
  container.innerHTML = `<div class="loading-row">Loading total balances…</div>`;
  try {
    const summary = await totalBalancesApi.getSummary();
    container.innerHTML = totalBalancePageHtml(summary);
  } catch (error) {
    if (error.status === 401) {
      onUnauthorized?.();
      return;
    }
    container.innerHTML = `<div class="card empty-state">${escapeHtml(error.message)}</div>`;
  }
}
