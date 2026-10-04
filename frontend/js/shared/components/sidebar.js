import { escapeHtml } from "../utils/format.js";
import { visiblePages } from "../../app/pageRegistry.js";
import { themeToggleHtml } from "./themeToggle.js";

export function sidebarHtml(activeRoute, user) {
  const links = visiblePages(user).map((page) => `
    <a class="nav-link ${activeRoute === page.route ? "active" : ""}" href="#/${page.route}">
      <span class="nav-icon" aria-hidden="true">${page.icon || "•"}</span><span>${escapeHtml(page.label)}</span>
    </a>
  `).join("");
  return `
    <aside class="sidebar">
      <div class="brand">BD</div>
      ${themeToggleHtml("theme-toggle-sidebar")}
      <nav class="nav" aria-label="Main navigation">${links}</nav>
      <div class="sidebar-preferences" data-timezone-selector-root></div>
      <div class="sidebar-user">
        <div class="sidebar-user-name">${escapeHtml(user?.username || "")}</div>
        <div class="sidebar-user-role">${escapeHtml(user?.role || "")}</div>
        <button class="sidebar-logout" type="button" data-logout>Sign out</button>
      </div>
    </aside>
  `;
}
