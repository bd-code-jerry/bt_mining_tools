import { escapeHtml } from "../../../shared/utils/format.js";

export function chooseWorkspaceForRole(user, workspaces, requestedWorkspaceId = null) {
  if (!Array.isArray(workspaces) || workspaces.length === 0) return null;
  if (user?.role === "admin") {
    const requested = workspaces.find((workspace) => Number(workspace.id) === Number(requestedWorkspaceId));
    return requested || workspaces.find((workspace) => workspace.kind === "shared") || workspaces[0];
  }
  if (user?.role === "member") return workspaces.find((workspace) => workspace.kind === "shared") || null;
  if (user?.role === "user") {
    return workspaces.find((workspace) =>
      workspace.kind === "private" && Number(workspace.owner_user_id) === Number(user.id)
    ) || null;
  }
  return null;
}

export function workspaceSelectorHtml({ role, workspaces, selectedWorkspaceId }) {
  if (role !== "admin") return "";
  const options = workspaces.map((workspace) => `
    <option value="${Number(workspace.id)}" ${Number(workspace.id) === Number(selectedWorkspaceId) ? "selected" : ""}>
      ${escapeHtml(workspace.display_name)}
    </option>
  `).join("");
  return `
    <label class="workspace-select-control">
      <span>Viewing workspace</span>
      <select class="input workspace-select" data-workspace-select aria-label="Workspace">${options}</select>
    </label>
  `;
}

export function workspaceContextHtml(workspace) {
  if (!workspace) return "";
  return `<div class="workspace-context">Workspace: <strong>${escapeHtml(workspace.display_name)}</strong></div>`;
}
