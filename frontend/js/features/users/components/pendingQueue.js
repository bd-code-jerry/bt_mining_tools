import { escapeHtml } from "../../../shared/utils/format.js";

function roleOptions() {
  return ["admin", "member", "user"].map((role) => `<option value="${role}" ${role === "member" ? "selected" : ""}>${role}</option>`).join("");
}

export function pendingQueueHtml(accounts = []) {
  if (!accounts.length) return `<div class="users-empty">No accounts are waiting for approval.</div>`;
  return `
    <div class="pending-account-list">
      ${accounts.map((account) => `
        <article class="pending-account">
          <div class="pending-account-copy">
            <strong>${escapeHtml(account.username)}</strong>
            <span>${escapeHtml(account.email || "No email")}</span>
            <small>Requested ${escapeHtml(account.created_at || "—")}</small>
          </div>
          <form class="pending-account-actions" data-action="approve-pending" data-user-id="${Number(account.id)}">
            <label>Assign role
              <select class="input" name="role">${roleOptions()}</select>
            </label>
            <button class="btn btn-primary" type="submit">Approve</button>
            <button class="btn btn-danger-soft" type="button" data-action="deny-pending" data-user-id="${Number(account.id)}">Deny</button>
          </form>
        </article>
      `).join("")}
    </div>
  `;
}
