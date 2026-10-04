export function parseRouteHash(hash, fallback = "") {
  const route = String(hash || "")
    .replace(/^#\/?/, "")
    .split("?")[0]
    .trim();
  return route || fallback;
}

export function routeHash(route) {
  return `#/${route}`;
}

export function navigateTo(route, location = globalThis.window?.location) {
  if (!location) return;
  const target = routeHash(route);
  if (location.hash === target) return false;
  location.hash = target;
  return true;
}
