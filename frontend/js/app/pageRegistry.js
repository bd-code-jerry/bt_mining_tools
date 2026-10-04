export const pageRegistry = [
  {
    route: "api-balances",
    label: "API key balances",
    icon: "⚿",
    capability: "balances:read",
    async render(container, options) {
      const { renderApiBalancesPage } = await import("../features/balances/page.js");
      return renderApiBalancesPage(container, options);
    },
  },
  {
    route: "total-balances",
    label: "Total Balance",
    icon: "Σ",
    capability: "total_balances:read",
    async render(container, options) {
      const { renderTotalBalancePage } = await import("../features/total-balances/page.js");
      return renderTotalBalancePage(container, options);
    },
  },
  {
    route: "users",
    label: "Users",
    icon: "♙",
    capability: "users:manage",
    async render(container, options) {
      const { renderUsersPage } = await import("../features/users/page.js");
      return renderUsersPage(container, options);
    },
  },
];

export function visiblePages(user, pages = pageRegistry) {
  const capabilities = new Set(user?.capabilities || []);
  return pages.filter((page) => capabilities.has(page.capability));
}

export function resolvePage(route, user, pages = pageRegistry) {
  const available = visiblePages(user, pages);
  return available.find((page) => page.route === route) || available[0] || null;
}
