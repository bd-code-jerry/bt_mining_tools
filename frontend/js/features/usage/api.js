import { request } from "../../shared/api/client.js";

export const usageApi = {
  getSummary: ({ period = "all", startDate = "", endDate = "", workspaceId = null } = {}) => {
    const params = new URLSearchParams({ period });
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (workspaceId != null) params.set("workspace_id", String(workspaceId));
    return request(`/api/usage/summary?${params.toString()}`);
  },
};
