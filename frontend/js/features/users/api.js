import { request } from "../../shared/api/client.js";

function filterQuery(filters = {}) {
  const params = new URLSearchParams();
  for (const key of ["start_date", "end_date", "account_id", "role"]) {
    const value = filters[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  }
  return params.size ? `?${params.toString()}` : "";
}

export const usersApi = {
  listAccounts: () => request("/api/users"),
  setRegistrationEnabled: (enabled) => request("/api/users/registration", {
    method: "PATCH",
    body: JSON.stringify({ enabled: Boolean(enabled) }),
  }),
  createAccount: (body) => request("/api/users", { method: "POST", body: JSON.stringify(body) }),
  approvePending: (userId, role) => request(`/api/users/pending/${Number(userId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ role }),
  }),
  denyPending: (userId) => request(`/api/users/pending/${Number(userId)}`, { method: "DELETE" }),
  setRole: (userId, role) => request(`/api/users/${Number(userId)}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  }),
  setStatus: (userId, status) => request(`/api/users/${Number(userId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  }),
  updateEmail: (userId, email) => request(`/api/users/${Number(userId)}`, {
    method: "PATCH",
    body: JSON.stringify({ email: email || null }),
  }),
  resetPassword: (userId, newPassword) => request(`/api/users/${Number(userId)}/password-reset`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  }),
  deleteAccount: (userId) => request(`/api/users/${Number(userId)}`, { method: "DELETE" }),
  getSessions: (userId) => request(`/api/users/${Number(userId)}/sessions`),
  revokeSessions: (userId) => request(`/api/users/${Number(userId)}/sessions`, { method: "DELETE" }),
  revokeSession: (sessionId) => request(`/api/users/sessions/${Number(sessionId)}`, { method: "DELETE" }),
  getLoginEvents: (filters = {}) => request(`/api/users/login-events${filterQuery(filters)}`),
  getDailyLoginCounts: (filters = {}) => request(`/api/users/login-events/daily${filterQuery(filters)}`),
};
