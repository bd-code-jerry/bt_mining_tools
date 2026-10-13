import test from "node:test";
import assert from "node:assert/strict";

import { pageRegistry, visiblePages, resolvePage } from "../frontend/js/app/pageRegistry.js";
import { parseRouteHash } from "../frontend/js/app/router.js";

test("balance navigation is available to every role while admin pages require the admin capability", () => {
  const registry = pageRegistry;
  const user = { role: "user", capabilities: ["expenses:read", "balances:read", "total_balances:read"] };
  const member = { role: "member", capabilities: ["expenses:read", "balances:read", "total_balances:read"] };
  const admin = { role: "admin", capabilities: ["expenses:read", "balances:read", "total_balances:read", "users:manage"] };

  assert.deepEqual(visiblePages(user, registry).map((page) => page.route), ["overview", "used", "api-balances", "total-balances"]);
  assert.deepEqual(visiblePages(member, registry).map((page) => page.route), ["overview", "used", "api-balances", "total-balances"]);
  assert.deepEqual(visiblePages(admin, registry).map((page) => page.route), ["overview", "used", "api-balances", "total-balances", "users"]);
});

test("route parsing uses Overview as the signed-in default and rejects inaccessible routes", () => {
  const member = { capabilities: ["expenses:read", "balances:read"] };
  assert.equal(parseRouteHash("", "overview"), "overview");
  assert.equal(parseRouteHash("#/api-balances?workspace_id=2", "api-balances"), "api-balances");
  assert.equal(resolvePage("users", member, pageRegistry).route, "overview");
});
