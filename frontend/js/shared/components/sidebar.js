import { escapeHtml } from "../utils/format.js";
import { visiblePages } from "../../app/pageRegistry.js";
import { themeToggleHtml } from "./themeToggle.js";

function pageLinkHtml(page, activeRoute) {
  const active = activeRoute === page.route;
  return `
    <a class="nav-link ${active ? "active" : ""}" href="#/${page.route}"${active ? ' aria-current="page"' : ""}>
      <span class="nav-icon" aria-hidden="true">${page.icon || "•"}</span><span>${escapeHtml(page.label)}</span>
    </a>
  `;
}

export function sidebarHtml(activeRoute, user) {
  const pages = visiblePages(user);
  const subnetPages = pages.filter((page) => page.group === "subnet-67");
  const primaryLinks = pages.filter((page) => !page.group && page.route !== "users").map((page) => pageLinkHtml(page, activeRoute)).join("");
  const adminLinks = pages.filter((page) => page.route === "users").map((page) => pageLinkHtml(page, activeRoute)).join("");
  const subnetOpen = subnetPages.some((page) => page.route === activeRoute);
  const subnetGroup = subnetPages.length ? `
    <details class="nav-group"${subnetOpen ? " open" : ""}>
      <summary class="nav-link nav-group-label"><span class="nav-icon" aria-hidden="true">⌘</span><span>67 API keys</span><span class="nav-group-chevron" aria-hidden="true">›</span></summary>
      <div class="nav-group-children">${subnetPages.map((page) => pageLinkHtml(page, activeRoute)).join("")}</div>
    </details>
  ` : "";
  return `
    <aside class="sidebar">
      <div class="brand">BD</div>
      ${themeToggleHtml("theme-toggle-sidebar")}
      <nav class="nav" aria-label="Main navigation">${primaryLinks}${subnetGroup}${adminLinks}</nav>
      <div class="sidebar-preferences" data-timezone-selector-root></div>
      <div class="sidebar-user">
        <div class="sidebar-user-name">${escapeHtml(user?.username || "")}</div>
        <div class="sidebar-user-role">${escapeHtml(user?.role || "")}</div>
        <button class="sidebar-logout" type="button" data-logout>Sign out</button>
      </div>
    </aside>
  `;
}
