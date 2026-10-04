import { request } from "../../shared/api/client.js";

function withWorkspace(path, workspaceId) {
  if (workspaceId == null) return path;
  const query = new URLSearchParams({ workspace_id: String(workspaceId) });
  return `${path}?${query.toString()}`;
}

export const balancesApi = {
  getOverview: (page = 1, pageSize = 5, workspaceId = null) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (workspaceId != null) params.set("workspace_id", String(workspaceId));
    return request(`/api/balances/overview?${params.toString()}`);
  },
  createHistory: (body, workspaceId = null) =>
    request(withWorkspace("/api/balances/history", workspaceId), { method: "POST", body: JSON.stringify(body) }),
  addBalances: (body, workspaceId = null) =>
    request(withWorkspace("/api/balances/add-balance", workspaceId), { method: "POST", body: JSON.stringify(body) }),
  getHistoryEntry: (id, workspaceId = null) =>
    request(withWorkspace(`/api/balances/history/${id}`, workspaceId)),
  updateHistory: (id, body, workspaceId = null) =>
    request(withWorkspace(`/api/balances/history/${id}`, workspaceId), { method: "PUT", body: JSON.stringify(body) }),
  deleteHistory: (id, workspaceId = null) =>
    request(withWorkspace(`/api/balances/history/${id}`, workspaceId), { method: "DELETE" }),
};
