# Adding a feature

The project groups backend and frontend code by feature. Keep a feature's page, API calls, business rules, data access, and tests near each other so later changes have an obvious home.

## 1. Define the page and access rule

Decide what the page does, which roles can use it, and whether its data belongs to the shared workspace, a user's private workspace, or all users in aggregate. Add a capability for the behavior, such as `reports:read`, rather than relying on a hidden frontend link.

Capabilities are listed by role in `backend/app/core/permissions.py`. The backend must enforce a capability on every protected API operation. `frontend/js/app/pageRegistry.js` uses the corresponding capability to decide whether to show the page in navigation; this is a user-interface rule, not the security boundary.

## 2. Add the backend feature

Create a package under `backend/app/features/<feature>/` with only the modules it needs:

```text
backend/app/features/reports/
├── __init__.py
├── router.py       # HTTP route definitions and request orchestration
├── schemas.py      # validated request and response shapes
├── service.py      # business rules and authorization decisions
└── repository.py   # SQL queries and persistence
```

Then:

1. Define request and response models in `schemas.py`.
2. Put route definitions in `router.py`; obtain the authenticated account through the shared dependency and check its capability.
3. Put business decisions in `service.py` and SQL in `repository.py`.
4. If the feature reads or writes workspace data, resolve the workspace through `backend/app/features/workspaces/service.py` before querying. Never trust a submitted workspace ID as authorization.
5. Register the router in `backend/app/api.py`.
6. Add Python tests under `tests/` for access control, validation, behavior, and persistence.

For a schema change, add a new ordered migration module under `backend/app/migrations/versions/` and register it in `backend/app/migrations/runner.py`. Migrations should be repeatable through the migration table, transactional, and covered by migration tests. Do not edit an already released migration to change an existing database.

## 3. Add the frontend feature

Create a folder under `frontend/js/features/<feature>/`:

```text
frontend/js/features/reports/
├── api.js          # feature-specific calls through the shared API client
├── page.js         # page rendering and event wiring
└── components/     # reusable pieces used only by this feature
```

Add a page-registry entry in `frontend/js/app/pageRegistry.js` with its route, label, icon, capability, and dynamic page import. The sidebar is generated from this registry and the signed-in account's capabilities, so the feature does not need its own navigation implementation. Reuse shared components and formatters from `frontend/js/shared/`.

Escape server values when rendering HTML. Let the backend decide whether an operation is allowed and show returned errors through the shared API client and toast patterns; hiding a button does not replace backend authorization.

## 4. Test and verify

Add Python `unittest` coverage for backend behavior and Node `.mjs` tests for frontend modules or pages. Run the full checks from the project root:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
git diff --check
```

For new roles or workspace behavior, test direct API requests with forged IDs and unauthorized writes in addition to checking which pages appear in navigation.

## Existing examples

- `backend/app/features/balances/` and `frontend/js/features/balances/` implement workspace-scoped balance history.
- `backend/app/features/users/` and `frontend/js/features/users/` implement admin account and login management.
- `backend/app/features/total_balances/` and `frontend/js/features/total-balances/` implement an all-role aggregate page without detailed history access.
