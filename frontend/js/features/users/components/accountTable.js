import { escapeHtml } from "../../../shared/utils/format.js";

const ROLES = ["admin", "member", "user"];

function roleOptions(currentRole) {
  return ROLES.map((role) => `<option value="${role}" ${currentRole === role ? "selected" : ""}>${role}</option>`).join("");
}

export function resetPasswordFormHtml(userId) {
  const id = Number(userId);
  return `
    <details class="user-reset-details">
      <summary>Reset password</summary>
      <form class="user-inline-form" data-action="reset-password" data-user-id="${id}">
        <label>New password
          <input class="input" type="password" name="new_password" minlength="8" maxlength="256" autocomplete="new-password" required />
        </label>
        <button class="btn btn-small" type="submit">Save password</button>
      </form>
    </details>
  `;
}

export function accountTableHtml(accounts = []) {
  if (!accounts.length) return `<div class="users-empty">No accounts to show.</div>`;
  const rows = accounts.map((account) => {
    const id = Number(account.id);
    const status = account.status || "active";
    const nextStatus = status === "active" ? "disabled" : "active";
    const email = account.email || "";
    return `
      <tr>
        <td>
          <strong>${escapeHtml(account.username)}</strong>
          <small class="users-account-id">Account #${id}</small>
        </td>
        <td>
          <form class="user-email-form" data-action="update-email" data-user-id="${id}">
            <input class="input" type="email" name="email" value="${escapeHtml(email)}" aria-label="Email for ${escapeHtml(account.username)}" />
            <button class="btn btn-small" type="submit">Save</button>
          </form>
        </td>
        <td>
          <label class="sr-only" for="account-role-${id}">Role for ${escapeHtml(account.username)}</label>
          <select id="account-role-${id}" class="input users-role-select" data-action="change-role" data-user-id="${id}">${roleOptions(account.role)}</select>
        </td>
        <td><span class="users-status status-${escapeHtml(status)}">${escapeHtml(status)}</span></td>
        <td>${escapeHtml(account.created_at || "—")}</td>
        <td>${escapeHtml(account.last_login_at || "Never")}</td>
        <td class="users-account-actions">
          <button class="btn btn-small" type="button" data-action="view-sessions" data-user-id="${id}">Sessions</button>
          <button class="btn btn-small" type="button" data-action="revoke-user-sessions" data-user-id="${id}">Revoke sessions</button>
          <button class="btn btn-small" type="button" data-action="toggle-status" data-user-id="${id}" data-next-status="${nextStatus}">${nextStatus === "disabled" ? "Disable" : "Enable"}</button>
          <button class="btn btn-danger-soft btn-small" type="button" data-action="delete-account" data-user-id="${id}">Delete</button>
          ${resetPasswordFormHtml(id)}
        </td>
      </tr>
    `;
  }).join("");
  return `
    <div class="table-wrap users-table-wrap">
      <table class="users-account-table">
        <thead><tr><th>Account</th><th>Email</th><th>Role</th><th>Status</th><th>Registered</th><th>Last login</th><th>Manage</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

export function sessionListHtml(userId, sessions = []) {
  const id = Number(userId);
  const sessionRows = sessions.length ? sessions.map((session) => `
    <tr>
      <td>${escapeHtml(session.created_at || "—")}</td>
      <td>${escapeHtml(session.last_activity_at || "—")}</td>
      <td>${escapeHtml(session.expires_at || "—")}</td>
      <td><button class="btn btn-danger-soft btn-small" type="button" data-action="revoke-session" data-session-id="${Number(session.id)}" data-user-id="${id}">Revoke</button></td>
    </tr>
  `).join("") : `<tr><td colspan="4" class="users-empty-cell">No active sessions.</td></tr>`;
  return `
    <section class="card users-sessions-panel">
      <div class="users-section-heading">
        <div><h2>Active sessions</h2><p class="help">Only active sessions are shown. Login history remains available after sign-out.</p></div>
        <button class="btn btn-danger-soft" type="button" data-action="revoke-user-sessions" data-user-id="${id}">Revoke all sessions</button>
      </div>
      <div class="table-wrap"><table><thead><tr><th>Signed in</th><th>Last activity</th><th>Expires</th><th></th></tr></thead><tbody>${sessionRows}</tbody></table></div>
    </section>
  `;
}
