import test from "node:test";
import assert from "node:assert/strict";

import { pageRegistry, visiblePages, resolvePage } from "../frontend/js/app/pageRegistry.js";
import { parseRouteHash } from "../frontend/js/app/router.js";

test("balance navigation is available to every role while admin pages require the admin capability", () => {
  const registry = pageRegistry;
  const user = { role: "user", capabilities: ["balances:read", "total_balances:read"] };
  const member = { role: "member", capabilities: ["balances:read", "total_balances:read"] };
  const admin = { role: "admin", capabilities: ["balances:read", "total_balances:read", "users:manage"] };

  assert.deepEqual(visiblePages(user, registry).map((page) => page.route), ["api-balances", "total-balances"]);
  assert.deepEqual(visiblePages(member, registry).map((page) => page.route), ["api-balances", "total-balances"]);
  assert.deepEqual(visiblePages(admin, registry).map((page) => page.route), ["api-balances", "total-balances", "users"]);
});

test("route parsing uses API balances as the signed-in default and rejects inaccessible routes", () => {
  const member = { capabilities: ["balances:read"] };
  assert.equal(parseRouteHash("", "api-balances"), "api-balances");
  assert.equal(parseRouteHash("#/api-balances?workspace_id=2", "api-balances"), "api-balances");
  assert.equal(resolvePage("users", member, pageRegistry).route, "api-balances");
});
