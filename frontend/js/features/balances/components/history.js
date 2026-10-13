import {
  escapeHtml,
  formatBalance,
  formatDateShort,
  numberValue,
} from "../../../shared/utils/format.js";

function visiblePageNumbers(currentPage, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const pages = new Set([1, totalPages, currentPage]);
  for (let offset = -2; offset <= 2; offset += 1) {
    const page = currentPage + offset;
    if (page >= 1 && page <= totalPages) pages.add(page);
  }
  return [...pages].sort((left, right) => left - right);
}

function paginationHtml(pagination = {}, prefix = "history") {
  const page = pagination.page || 1;
  const totalPages = pagination.total_pages || 1;
  const pageSize = pagination.page_size || 5;
  const totalItems = pagination.total_items || 0;
  let previousPage = null;
  const buttons = visiblePageNumbers(page, totalPages).map((pageNumber) => {
    const gap = previousPage !== null && pageNumber - previousPage > 1
      ? `<span class="pagination-gap">…</span>`
      : "";
    previousPage = pageNumber;
    return `${gap}<button class="page-btn ${pageNumber === page ? "active" : ""}" type="button" data-${prefix}-page="${pageNumber}">${pageNumber}</button>`;
  }).join("");

  return `
    <div class="pagination-bar">
      <div class="pagination-info">${totalItems} saved ${totalItems === 1 ? "entry" : "entries"}</div>
      <div class="pagination-controls">
        <button class="page-btn" type="button" data-${prefix}-page="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""}>‹</button>
        ${buttons}
        <button class="page-btn" type="button" data-${prefix}-page="${Math.min(totalPages, page + 1)}" ${page >= totalPages ? "disabled" : ""}>›</button>
      </div>
      <label class="page-size-control">
        <span>Rows</span>
        <select class="page-size-select" data-${prefix}-page-size>
          ${[5, 10, 20, 50].map((size) => `<option value="${size}" ${size === pageSize ? "selected" : ""}>${size}</option>`).join("")}
        </select>
      </label>
    </div>
  `;
}

function usdUsage(entry) {
  return (entry.values || [])
    .filter((value) => value.unit === "USD")
    .reduce((sum, value) => sum + numberValue(value.used_balance), 0);
}

export function balanceHistoryTableHtml(overview, { canWrite = false } = {}) {
  const providers = overview.providers || [];
  const history = overview.history || [];
  if (!history.length) {
    return `<div class="empty-state">No saved balance history yet.</div>${paginationHtml(overview.pagination)}`;
  }

  const providerHeaders = providers.map((provider) => `
    <th colspan="3">${escapeHtml(provider.display_name)}<span class="subhead">Total &nbsp;&nbsp; Used &nbsp;&nbsp; Left</span></th>
  `).join("");
  const rows = history.map((entry) => {
    const values = Object.fromEntries((entry.values || []).map((value) => [value.provider_key, value]));
    const cells = providers.map((provider) => {
      const value = values[provider.provider_key];
      return `
        <td>${formatBalance(value?.total_balance ?? 0, provider.unit)}</td>
        <td>${formatBalance(value?.used_balance ?? 0, provider.unit)}</td>
        <td>${formatBalance(value?.left_balance ?? 0, provider.unit)}</td>
      `;
    }).join("");
    const actions = canWrite ? `
      <td class="history-actions">
        <div class="history-action-buttons">
          <button class="btn btn-soft btn-small" type="button" data-edit-entry="${Number(entry.id)}">✎ Edit</button>
          ${entry.entry_kind === "legacy" ? `<button class="btn btn-soft btn-small" type="button" data-classify-entry="${Number(entry.id)}">Classify top-up</button>` : ""}
          <button class="btn btn-danger-soft btn-small" type="button" data-delete-entry="${Number(entry.id)}" data-entry-date="${escapeHtml(entry.entry_date)}">Delete</button>
        </div>
      </td>
    ` : "";
    return `
      <tr>
        <td>${formatDateShort(entry.entry_date)}${entry.entry_kind === "legacy" ? '<span class="subhead legacy-label">Legacy / unclassified</span>' : ""}</td>
        ${cells}
        <td class="history-total">${formatBalance(usdUsage(entry), "USD")}</td>
        ${actions}
      </tr>
    `;
  }).join("");

  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Date</th>${providerHeaders}<th>Total Used<span class="subhead">USD only</span></th>${canWrite ? "<th>Actions</th>" : ""}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    ${paginationHtml(overview.pagination)}
  `;
}


export function addedBalanceHistoryTableHtml(overview, { canWrite = false } = {}) {
  const entries = overview.topup_history || [];
  if (!entries.length) {
    return `<div class="empty-state">No added balance history yet.</div>${paginationHtml(overview.topup_pagination, "topup")}`;
  }
  const rows = entries.flatMap((entry) => {
    const additions = (entry.values || []).filter((value) => numberValue(value.added_balance) > 0);
    return additions.map((value, index) => `<tr>
      ${index === 0 ? `<td rowspan="${additions.length}">${formatDateShort(entry.entry_date)}</td>` : ""}
      <td><strong>${escapeHtml(value.display_name)}</strong></td>
      <td>${formatBalance(value.balance_before, value.unit)}</td>
      <td class="topup-amount">${formatBalance(value.added_balance, value.unit)}</td>
      <td>${formatBalance(value.left_balance, value.unit)}</td>
      <td>${escapeHtml(value.unit)}</td>
      ${canWrite && index === 0 ? `<td rowspan="${additions.length}" class="history-actions"><div class="history-action-buttons">
        <button class="btn btn-soft btn-small" type="button" data-edit-topup="${Number(entry.id)}">✎ Edit</button>
        <button class="btn btn-danger-soft btn-small" type="button" data-delete-entry="${Number(entry.id)}" data-entry-date="${escapeHtml(entry.entry_date)}">Delete</button>
      </div></td>` : ""}
    </tr>`);
  }).join("");
  return `<div class="table-wrap"><table class="topup-history-table">
    <thead><tr><th>Date</th><th>API provider</th><th>Balance before</th><th>Amount added</th><th>Balance after</th><th>Unit</th>${canWrite ? "<th>Actions</th>" : ""}</tr></thead>
    <tbody>${rows}</tbody></table></div>${paginationHtml(overview.topup_pagination, "topup")}`;
}
