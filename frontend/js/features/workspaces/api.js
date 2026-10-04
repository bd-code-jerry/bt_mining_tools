import { request } from "../../shared/api/client.js";

export const workspacesApi = {
  getWorkspaces: () => request("/api/workspaces"),
};
