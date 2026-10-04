import { escapeHtml } from "../../../shared/utils/format.js";

export function userTimezoneLabel(timezone) {
  return timezone === "America/New_York" ? "Eastern Time (ET)" : "UTC";
}

function accountOptions(accounts, selectedId) {
  const options = [`<option value="">All accounts</option>`];
  for (const account of accounts) {
    const id = String(account.id);
    const label = `${account.username}${account.email ? ` — ${account.email}` : ""}`;
    options.push(`<option value="${Number(account.id)}" ${String(selectedId) === id ? "selected" : ""}>${escapeHtml(label)}</option>`);
  }
  return options.join("");
}

function dailyChart(days = []) {
  if (!days.length) return `<div class="users-empty">No daily sign-in data for this range.</div>`;
  const maxCount = Math.max(1, ...days.map((day) => Math.max(0, Number(day.count) || 0)));
  return `
    <div class="daily-login-chart" aria-label="Daily sign-in counts">
      ${days.map((day) => {
        const count = Math.max(0, Number(day.count) || 0);
        const width = Math.round((count / maxCount) * 100);
        return `
          <div class="daily-login-row">
            <time datetime="${escapeHtml(day.date)}">${escapeHtml(day.date)}</time>
            <div class="daily-login-track"><span class="daily-login-bar" style="width:${width}%"></span></div>
            <strong>${count} ${count === 1 ? "sign-in" : "sign-ins"}</strong>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function eventTable(events = []) {
  if (!events.length) return `<div class="users-empty">No login events match these filters.</div>`;
  return `
    <div class="table-wrap">
      <table class="login-event-table">
        <thead><tr><th>Account</th><th>Role at sign-in</th><th>Signed in</th></tr></thead>
        <tbody>${events.map((event) => `
          <tr>
            <td><strong>${escapeHtml(event.username)}</strong><small>${escapeHtml(event.email || "No email")}</small></td>
            <td>${escapeHtml(event.role)}</td>
            <td><time>${escapeHtml(event.signed_in_at)}</time></td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>
  `;
}

export function loginActivityHtml({ accounts = [], filters = {}, events = [], days = [], timezone = "UTC" } = {}) {
  return `
    <section class="card users-section-card">
      <div class="users-section-heading">
        <div><h2>Login activity</h2><p class="help">Sign-in history is retained after logout. Times and daily totals use ${userTimezoneLabel(timezone)}.</p></div>
      </div>
      <p class="help">Use From by itself to include through today, or To by itself to include the prior 30 days.</p>
      <form class="login-filter-form" data-action="filter-login-activity">
        <label>From<input class="input" type="date" name="start_date" value="${escapeHtml(filters.start_date || "")}" /></label>
        <label>To<input class="input" type="date" name="end_date" value="${escapeHtml(filters.end_date || "")}" /></label>
        <label>Account<select class="input" name="account_id">${accountOptions(accounts, filters.account_id)}</select></label>
        <label>Role<select class="input" name="role">
          <option value="" ${!filters.role ? "selected" : ""}>All roles</option>
          ${["admin", "member", "user"].map((role) => `<option value="${role}" ${filters.role === role ? "selected" : ""}>${role}</option>`).join("")}
        </select></label>
        <button class="btn btn-primary" type="submit">Apply filters</button>
        <button class="btn" type="button" data-action="clear-login-filters">Clear</button>
      </form>
      <div class="login-activity-grid">
        <div class="login-daily-panel"><h3>Sign-ins per day</h3>${dailyChart(days)}</div>
        <div class="login-events-panel"><h3>Recent sign-ins</h3>${eventTable(events)}</div>
      </div>
    </section>
  `;
}
