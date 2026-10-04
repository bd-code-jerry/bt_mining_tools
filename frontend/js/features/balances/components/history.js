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

function paginationHtml(pagination = {}) {
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
    return `${gap}<button class="page-btn ${pageNumber === page ? "active" : ""}" type="button" data-history-page="${pageNumber}">${pageNumber}</button>`;
  }).join("");

  return `
    <div class="pagination-bar">
      <div class="pagination-info">${totalItems} saved ${totalItems === 1 ? "entry" : "entries"}</div>
      <div class="pagination-controls">
        <button class="page-btn" type="button" data-history-page="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""}>‹</button>
        ${buttons}
        <button class="page-btn" type="button" data-history-page="${Math.min(totalPages, page + 1)}" ${page >= totalPages ? "disabled" : ""}>›</button>
      </div>
      <label class="page-size-control">
        <span>Rows</span>
        <select class="page-size-select" data-history-page-size>
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
    <th colspan="2">${escapeHtml(provider.display_name)}<span class="subhead">Used &nbsp;&nbsp;&nbsp;&nbsp; Left</span></th>
  `).join("");
  const rows = history.map((entry) => {
    const values = Object.fromEntries((entry.values || []).map((value) => [value.provider_key, value]));
    const cells = providers.map((provider) => {
      const value = values[provider.provider_key];
      return `
        <td>${formatBalance(value?.used_balance ?? 0, provider.unit)}</td>
        <td>${formatBalance(value?.left_balance ?? 0, provider.unit)}</td>
      `;
    }).join("");
    const actions = canWrite ? `
      <td class="history-actions">
        <div class="history-action-buttons">
          <button class="btn btn-soft btn-small" type="button" data-edit-entry="${Number(entry.id)}">✎ Edit</button>
          <button class="btn btn-danger-soft btn-small" type="button" data-delete-entry="${Number(entry.id)}" data-entry-date="${escapeHtml(entry.entry_date)}">Delete</button>
        </div>
      </td>
    ` : "";
    return `
      <tr>
        <td>${formatDateShort(entry.entry_date)}</td>
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
