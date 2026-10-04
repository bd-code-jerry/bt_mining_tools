# Role-Based Workspaces and User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add approved registration, admin account controls, role-based shared and private workspaces, login reporting, an all-role Total Balance page, and an account-level UTC/ET time zone preference.

**Architecture:** Keep FastAPI, SQLite, and vanilla JavaScript. Apply ordered SQLite migrations before serving requests, then enforce roles and workspace scope in backend feature services. Put auth, users, workspaces, balances, usage, and total-balance code in separate feature modules; expose aggregate cross-workspace data only through the dedicated Total Balance summary API.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, Pydantic, vanilla JavaScript ES modules, Python `unittest`, and Node's built-in test runner.

**Spec:** `docs/superpowers/specs/2026-10-01-user-management-workspaces-design.md`

## Global Constraints

- Use one SQLite database at `BD_DATABASE_PATH`, defaulting to `data/bd_dashboard.db`.
- Provide the `admin`, `member`, and `user` roles with server-enforced permissions.
- Every balance and usage query requires an authorized workspace context.
- `total_balances:read` exposes aggregate summaries only; it does not grant access to detailed history.
- New self-registrations remain pending until an admin approves them.
- Keep the current UI framework dependency-free and vanilla JavaScript.
- Let every signed-in account choose UTC or Eastern Time (ET), default to UTC, and persist the preference per account.
- Store event timestamps in UTC and group login days in the viewing admin's selected zone; preserve balance entry dates as date-only values.
- The user's BD-only configuration remains authoritative; do not add `RSG_*` environment fallbacks.
- Keep future Dashboard, Settings, Wallets, and Tao State behavior out of scope; provide the feature-module extension pattern without empty pages.

## Review Focus

- First-registration concurrency must yield one active admin; invalid legacy admin configuration must leave the database unchanged; pin both in Tasks 1-2 with `test_concurrent_first_registrations_create_one_admin` and `test_invalid_initial_admin_leaves_legacy_database_unchanged`.
- Forged workspace IDs and write requests must never expand member or user access; pin this in Task 3 with `test_workspace_id_cannot_escalate_role` and `test_member_cannot_mutate_shared_balances`.
- Identifier lifecycle and account deletion must preserve uniqueness and shared history while releasing denied identifiers and removing a deleted user's private data; pin this in Tasks 2 and 4 with `test_duplicate_identifier_lifecycle` and `test_last_admin_protection_and_private_workspace_deletion`.
- All roles can save only their own supported UTC/ET preference; timestamps stay correct around UTC midnight and ET daylight-saving transitions; pin this in Tasks 1, 4, and 6 with the timezone migration, API, and display tests.

---

### Task 1: Versioned database migrations and BD configuration

**Files:**
- Create: `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/database.py`
- Create: `backend/app/migrations/__init__.py`, `backend/app/migrations/runner.py`, `backend/app/migrations/versions/__init__.py`, `backend/app/migrations/versions/v001_base_schema.py`, `backend/app/migrations/versions/v002_roles_workspaces.py`, `backend/app/migrations/versions/v003_timezone_preference.py`
- Modify: `backend/app/config.py`, `backend/app/database.py`, `backend/app/main.py`, `backend/app/services/balance_service.py` (temporary shared-workspace compatibility), `tests/test_balance_integrity.py`, `.env.example`
- Keep `backend/app/config.py` and `backend/app/database.py` as small re-export shims so existing project imports continue to work; `backend/app/core/` owns the implementation.
- Create: `requirements-dev.txt` with `-r requirements.txt` and `httpx>=0.27,<1.0` for FastAPI `TestClient` coverage
- Create: `tests/support.py`
- Test: `tests/test_config.py`, `tests/test_migrations.py`

**Interfaces:**
- Produces: `migrate_database(database_path: Path, *, initial_admin_username: str | None) -> None`; `db_connection() -> Iterator[sqlite3.Connection]`; config exports `DATABASE_PATH`, `INITIAL_ADMIN_USERNAME`, and the existing `BD_*` runtime settings.
- Migration v001 creates the current base schema on a fresh database. Migration v002 adds roles, account status and email fields, login events, sessions' last-activity field, workspaces, and registration settings. Migration v003 adds `users.timezone`, limited to `UTC` and `America/New_York`, defaulting existing and new users to UTC. The runner creates and updates the schema-version table.

- [x] **Step 1: Write migration/config tests** named `test_invalid_initial_admin_leaves_legacy_database_unchanged`, `test_existing_database_backup_contains_pre_migration_schema`, `test_existing_users_receive_selected_admin_and_member_roles`, `test_fresh_database_does_not_require_initial_admin`, `test_migrations_are_repeatable`, and `test_migrated_users_default_to_utc`. Verify provider rows, balance values, user attribution, and existing sessions survive; legacy history belongs to the shared workspace; migrated accounts have no email and start with blank last-login data; and legacy accounts start with no reconstructed login events.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_migrations.py' -v`** and confirm the migration tests fail against the current unversioned schema.
- [x] **Step 3: Implement BD-only settings and the ordered migration runner.** Since `core/config.py` is one directory deeper than the existing config module, resolve the project root from `Path(__file__).resolve().parents[3]`. Validate `BD_INITIAL_ADMIN_USERNAME` against the existing user table before writes; create a SQLite backup with `Connection.backup()` at `DATABASE_PATH.parent / "backups" / "<database-name>.<UTC timestamp>.pre-migration.sqlite3"`; apply each schema/data migration transactionally; rebuild history tables as needed so `workspace_id` is required and existing rows point to the shared workspace. Keep the runner idempotent, seed providers only after migrations complete, and include the database path and migration version in startup errors without exposing secrets. Until Task 3 moves the legacy balance service into its workspace-aware feature, have its history inserts explicitly use the shared workspace. Update the existing non-local-host test to use `BD_*` variables.
- [x] **Step 4: Run `python -m unittest discover -s tests -p 'test_migrations.py' -v` and `python -m unittest discover -s tests -p 'test_config.py' -v`**; confirm all migration and BD-only setting tests pass, including repeat startup and unchanged legacy data after invalid bootstrap configuration.
- [x] **Step 5: Commit** as `feat: add versioned workspace migrations`.

### Task 2: Authentication, approval-aware registration, and core permissions

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/core/dependencies.py`, `backend/app/core/permissions.py`
- Create: `backend/app/features/__init__.py`, `backend/app/features/auth/__init__.py`, `backend/app/features/auth/router.py`, `backend/app/features/auth/schemas.py`, `backend/app/features/auth/service.py`, `backend/app/features/auth/repository.py`
- Modify: `backend/app/security.py` and `backend/app/dependencies.py` into re-export shims until the remaining balance/usage routers move in Task 3.
- Remove after imports move: `backend/app/routers/auth.py`
- Create: `backend/app/api.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `db_connection()` and the migrated tables from Task 1.
- Produces: `register_account(conn, *, username: str, email: str, password: str, registration_code: str | None) -> dict`; `authenticate(conn, identifier: str, password: str) -> dict`; `create_session(conn, user_id: int, role: str) -> tuple[str, int]`; `get_current_user(request: Request) -> dict`; `capabilities_for_role(role: str) -> list[str]`; `require_capability(user: dict, capability: str) -> None`. `/api/auth/me` returns the active user's role, capabilities, and persisted timezone.
- `register_account` returns the active admin only for the first successful registration; later accounts are pending and receive no session. Session creation writes one login event in the same transaction and returns the raw token only to the router for the HttpOnly cookie.

- [x] **Step 1: Write tests** named `test_first_registration_becomes_admin`, `test_later_registration_is_pending_without_session`, `test_login_accepts_username_or_email`, `test_pending_and_disabled_users_cannot_sign_in`, `test_duplicate_identifier_lifecycle`, `test_registration_code_is_enforced`, `test_failed_login_creates_no_event`, and `test_concurrent_first_registrations_create_one_admin`.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_auth.py' -v`** and confirm the new account-state and login tests fail.
- [x] **Step 3: Implement the auth feature and core session/capability checks.** Use `BEGIN IMMEDIATE` around first-account selection and creation; enforce case-insensitive username/email uniqueness; keep pending users sessionless; update `last_login_at` and persist the sign-in role on each successful new session; update `last_activity_at` for valid sessions; reject pending or disabled users on every authenticated request.
- [x] **Step 4: Run `python -m unittest discover -s tests -p 'test_auth.py' -v`** and confirm all auth, duplicate, and concurrency tests pass.
- [x] **Step 5: Commit** as `feat: add approval-aware authentication`.

### Task 3: Workspace authorization and workspace-scoped balance/usage APIs

**Files:**
- Create: `backend/app/features/workspaces/__init__.py`, `backend/app/features/workspaces/router.py`, `backend/app/features/workspaces/schemas.py`, `backend/app/features/workspaces/service.py`, `backend/app/features/workspaces/repository.py`
- Create: `backend/app/features/balances/__init__.py`, `backend/app/features/balances/router.py`, `backend/app/features/balances/schemas.py`, `backend/app/features/balances/service.py`, `backend/app/features/balances/repository.py`, `backend/app/features/balances/provider_catalog.py`
- Create: `backend/app/features/usage/__init__.py`, `backend/app/features/usage/router.py`, `backend/app/features/usage/schemas.py`, `backend/app/features/usage/service.py`, `backend/app/features/usage/repository.py`
- Remove after imports move: `backend/app/routers/balances.py`, `backend/app/routers/usage.py`, `backend/app/routers/__init__.py`, `backend/app/security.py`, `backend/app/dependencies.py`, `backend/app/services/balance_service.py`, `backend/app/services/usage_service.py`, `backend/app/services/seed_service.py`, `backend/app/services/__init__.py`
- Modify: `backend/app/core/permissions.py`, `backend/app/api.py`
- Test: `tests/test_workspace_permissions.py`, `tests/test_balance_integrity.py`, `tests/test_usage_scoping.py`

**Interfaces:**
- Consumes: active authenticated users and capabilities from Task 2.
- Produces: `resolve_workspace(conn, user: dict, requested_workspace_id: int | None, *, write: bool = False) -> dict`; `GET /api/workspaces` returns all workspaces to admins and the actor's allowed workspace to other roles; workspace-scoped `overview`, history mutation, and usage-summary service functions that all receive a resolved `workspace_id`. Balance/usage detail routes accept an optional `workspace_id`, which is validated by `resolve_workspace`.
- Admins may select any workspace; omitted selection defaults to shared. Members resolve to shared only and are read-only. Users resolve to their own private workspace and may edit only that workspace.

- [x] **Step 1: Write tests** named `test_admin_can_select_any_workspace`, `test_member_reads_shared_workspace_only`, `test_member_cannot_mutate_shared_balances`, `test_user_reads_and_edits_own_workspace_only`, `test_workspace_id_cannot_escalate_role`, and `test_usage_and_history_are_workspace_scoped`. Assert forbidden workspace access returns `403` and an unknown workspace returns `404`.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_workspace_permissions.py' -v`** and confirm requests currently ignore workspace boundaries or permit writes.
- [x] **Step 3: Move balance and usage SQL into feature repositories and require a resolved workspace for every read/write.** Add a private-workspace creation/reuse helper for later role assignment; preserve the workspace when an account changes away from and back to the `user` role. Scope pagination, latest entry, history detail, edit/delete, and range summaries by workspace ID. Move provider seeding into `features/balances/provider_catalog.py`.
- [x] **Step 4: Run `python -m unittest discover -s tests -p 'test_workspace_permissions.py' -v`, `python -m unittest discover -s tests -p 'test_balance_integrity.py' -v`, and `python -m unittest discover -s tests -p 'test_usage_scoping.py' -v`**; confirm no shared/private data crosses workspace boundaries and existing calculation/concurrency tests pass.
- [x] **Step 5: Commit** as `feat: scope balances and usage by workspace`.

### Task 4: Admin account controls and login activity APIs

**Files:**
- Create: `backend/app/features/users/__init__.py`, `backend/app/features/users/router.py`, `backend/app/features/users/schemas.py`, `backend/app/features/users/service.py`, `backend/app/features/users/repository.py`
- Create: `backend/app/features/preferences/__init__.py`, `backend/app/features/preferences/router.py`, `backend/app/features/preferences/schemas.py`, `backend/app/features/preferences/service.py`, `backend/app/features/preferences/repository.py`
- Modify: `backend/app/features/auth/service.py`, `backend/app/features/workspaces/service.py`, `backend/app/api.py`
- Test: `tests/test_user_management.py`, `tests/test_login_activity.py`, `tests/test_preferences.py`

**Interfaces:**
- Consumes: auth/session interfaces from Task 2 and workspace lifecycle from Task 3.
- Produces: admin-only service operations for pending approval/denial, direct account creation, role changes, disable/enable, password reset, deletion, registration toggle, session revocation/listing, login-event filtering, and daily counts; plus an authenticated preference operation allowing all roles to update only their own timezone. Admin login timestamps and daily counts use the viewing admin's saved timezone.
- Admin HTTP resources use `GET/POST /api/users`, `GET /api/users/pending`, `POST /api/users/pending/{user_id}/approve`, `DELETE /api/users/pending/{user_id}`, `PATCH /api/users/{user_id}/role`, `PATCH /api/users/{user_id}/status`, `POST /api/users/{user_id}/password-reset`, `DELETE /api/users/{user_id}`, `GET /api/users/{user_id}/sessions`, `DELETE /api/users/{user_id}/sessions`, `DELETE /api/users/sessions/{session_id}`, `PATCH /api/users/registration`, `GET /api/users/login-events`, and `GET /api/users/login-events/daily`; every route requires `users:manage`. Register static login-event routes before dynamic `user_id` routes.

- [x] **Step 1: Write tests** named `test_admin_approval_assigns_role`, `test_duplicate_identifier_lifecycle`, `test_denial_releases_identifiers`, `test_registration_toggle_blocks_self_registration_but_allows_admin_creation`, `test_role_changes_create_and_reuse_private_workspace`, `test_reset_and_disable_revoke_sessions`, `test_login_events_survive_logout_and_daily_counts_match`, `test_last_admin_protection_and_private_workspace_deletion`, `test_timezone_preference_is_per_account_and_available_to_all_roles`, `test_unsupported_timezone_is_rejected`, `test_login_daily_buckets_follow_viewer_timezone`, and `test_et_timezone_handles_dst_transition`. Verify the last enabled admin cannot be disabled, demoted, or deleted. Also assert event filters and active-session rows expose timestamps but no tokens or IP addresses.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_user_management.py' -v` and `python -m unittest discover -s tests -p 'test_login_activity.py' -v`** and confirm the admin workflows are not implemented.
- [x] **Step 3: Implement the users and preferences features.** Use one transaction for each state change; never return password hashes or plaintext passwords; do not record IPs or tokens in login events; delete private workspace/history/login events only on permanent user deletion; retain shared history and clear its deleted-user attribution through existing foreign-key behavior. Allow only `UTC` and `America/New_York` for the authenticated account's preference. Store event timestamps in UTC and apply the viewer's saved timezone to login-event display and daily grouping; keep balance entry dates as date-only values.
- [x] **Step 4: Run both user-management test modules and `python -m unittest discover -s tests -p 'test_preferences.py' -v`**; confirm role/status/session rules, viewer-local daily event counts, DST handling, and last-admin protection pass.
- [x] **Step 5: Commit** as `feat: add admin user and login management`.

### Task 5: Read-only Total Balance summary API

**Files:**
- Create: `backend/app/features/total_balances/__init__.py`, `backend/app/features/total_balances/router.py`, `backend/app/features/total_balances/schemas.py`, `backend/app/features/total_balances/service.py`, `backend/app/features/total_balances/repository.py`
- Modify: `backend/app/core/permissions.py`, `backend/app/api.py`
- Test: `tests/test_total_balances.py`

**Interfaces:**
- Consumes: workspaces and history repositories from Task 3.
- Produces: `get_total_balance_summary(conn) -> dict` and `GET /api/total-balances/summary`, protected by `total_balances:read` for admin, member, and user.
- Response shape: `{"workspaces": [{"workspace_id", "workspace_kind", "label", "values": [{"provider_key", "display_name", "unit", "total_balance", "left_balance", "total_spent"}]}], "team_totals": [{"provider_key", "display_name", "unit", "total_balance", "left_balance", "total_spent"}]}`. The endpoint returns no dated history entries or edit fields.

- [x] **Step 1: Write tests** for each workspace's latest total/left values, cumulative `used_balance`, correct team sums, empty workspaces, provider/unit separation, and response absence of history IDs/dates/details. Verify all three roles can call it while workspace history permissions stay unchanged.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_total_balances.py' -v`** and confirm the summary API is missing.
- [x] **Step 3: Implement the dedicated aggregate repository/service/router.** Select the latest history entry by `entry_date DESC, id DESC`, sum usage across history per workspace/provider, and sum workspace metrics per provider for team totals.
- [x] **Step 4: Run `python -m unittest discover -s tests -p 'test_total_balances.py' -v`** and confirm summary totals and privacy assertions pass.
- [x] **Step 5: Commit** as `feat: add role-visible total balance summaries`.

### Task 6: Frontend page registry, shared client, and auth states

**Files:**
- Create: `frontend/js/app/router.js`, `frontend/js/app/pageRegistry.js`
- Create: `frontend/js/shared/api/client.js`, `frontend/js/shared/components/sidebar.js`, `frontend/js/shared/components/themeToggle.js`, `frontend/js/shared/components/modal.js`, `frontend/js/shared/components/toast.js`, `frontend/js/shared/utils/format.js`
- Create: `frontend/js/features/auth/page.js`, `frontend/js/features/auth/api.js`
- Create: `frontend/js/features/preferences/api.js`, `frontend/js/shared/components/timezoneSelector.js`
- Modify: `frontend/js/app.js`, `frontend/index.html`
- Remove after imports move: `frontend/js/api/client.js`, `frontend/js/components/modal.js`, `frontend/js/components/sidebar.js`, `frontend/js/components/themeToggle.js`, `frontend/js/components/toast.js`, `frontend/js/utils/format.js`, `frontend/js/pages/loginPage.js`, `frontend/js/pages/registerPage.js`, `frontend/js/pages/dashboardPage.js`
- Test: `tests/test_page_registry.mjs`, `tests/test_auth_pages.mjs`, `tests/test_timezone_selector.mjs`, existing theme tests

**Interfaces:**
- Consumes: `/api/auth/me` capability payload and auth APIs from Task 2.
- Produces: a page registry whose entries define `route`, `label`, `render`, and required capability; a shared fetch/error-handling API client; router dispatch that checks login state and required capabilities. Each feature keeps its endpoint methods in its own `api.js`. `/api/auth/me` provides the authenticated account's persisted timezone to the shell.
- Existing theme state and theme toggle behavior remain available through shared modules.

- [x] **Step 1: Write Node tests** for role/capability route visibility, pending registration messaging, username-or-email sign-in, required email entry, case-insensitive duplicate error display, closed-registration messaging, authenticated landing on API balances, theme control availability on auth and signed-in shells, and timezone selector visibility and updates for all signed-in roles.
- [x] **Step 2: Run `node --test tests/test_page_registry.mjs tests/test_auth_pages.mjs`** and confirm new registry/auth expectations fail.
- [x] **Step 3: Refactor the app shell into app/shared/auth modules.** Remove the existing empty Dashboard placeholder from navigation and route post-login users to API balances; this leaves the future Dashboard feature to be added when its behavior is defined. Add required email input; show pending approval without invoking signed-in navigation; render routes from the registry; derive visible nav items from the authenticated user's capabilities; add a signed-in timezone selector for all roles, backed by the account preference API.
- [x] **Step 4: Run `node --test tests/test_page_registry.mjs tests/test_auth_pages.mjs tests/test_timezone_selector.mjs tests/test_theme_state.mjs tests/test_theme_ui.mjs`** and confirm all frontend routing, auth, timezone, and theme tests pass.
- [x] **Step 5: Commit** as `refactor: organize frontend routes and shared modules`.

### Task 7: Workspace-aware balance UI and Total Balance page

**Files:**
- Create: `frontend/js/features/workspaces/api.js`, `frontend/js/features/workspaces/components/workspaceSelector.js`
- Create: `frontend/js/features/balances/page.js`, `frontend/js/features/balances/api.js`, `frontend/js/features/balances/providerUi.js`, `frontend/js/features/balances/components/history.js`
- Create: `frontend/js/features/usage/api.js`, `frontend/js/features/usage/components/usageRangeSummary.js`
- Create: `frontend/js/features/total-balances/page.js`, `frontend/js/features/total-balances/api.js`, `frontend/styles/totalBalances.css`
- Modify: `frontend/js/app/pageRegistry.js`, `frontend/js/shared/components/sidebar.js`, `frontend/styles/balances.css`
- Remove after imports move: `frontend/js/pages/apiBalancesPage.js`, `frontend/js/components/usageRangeSummary.js`, `frontend/js/config/providerUi.js`
- Test: `tests/test_balance_pages.mjs`, `tests/test_total_balance_page.mjs`

**Interfaces:**
- Consumes: balance/usage and total-balance APIs from Tasks 3 and 5; admin workspace list from Task 3.
- Produces: an admin-only workspace selector; read-only balance UI for members; editable balance UI for admins and users in their authorized workspace; a read-only Total Balance page registered for all roles.

- [x] **Step 1: Write UI tests** that verify member controls cannot create/edit/delete entries, users call only their private workspace, admins include selected workspace IDs, the Total Balance page calls only `/api/total-balances/summary` and renders each workspace plus team totals without mixed units, and timezone changes never modify date-only balance values.
- [x] **Step 2: Run `node --test tests/test_balance_pages.mjs tests/test_total_balance_page.mjs`** and confirm the role-aware views and page do not yet exist.
- [x] **Step 3: Move the existing balances page into its feature folder and add role/workspace state.** Add the Total Balance renderer with per-workspace rows and a team total; escape displayed labels, format values using provider units, and keep other workspaces' dated history out of the page.
- [x] **Step 4: Run the two page tests plus all existing theme tests** and confirm navigation, read-only behavior, workspace selection, and aggregate rendering pass.
- [x] **Step 5: Commit** as `feat: add workspace balance and totals pages`.

### Task 8: Admin user-management and login-reporting page

**Files:**
- Create: `frontend/js/features/users/page.js`, `frontend/js/features/users/api.js`, `frontend/js/features/users/components/accountTable.js`, `frontend/js/features/users/components/pendingQueue.js`, `frontend/js/features/users/components/loginActivity.js`
- Create: `frontend/styles/users.css`
- Modify: `frontend/js/app/pageRegistry.js`, `frontend/js/shared/components/sidebar.js`, `frontend/index.html`
- Test: `tests/test_user_management_page.mjs`

**Interfaces:**
- Consumes: users APIs from Task 4 and `users:manage` capability from Task 2.
- Produces: admin-only navigation and page with pending approvals, direct account creation, account/status/role controls, registration/last-login details, password reset, deletion confirmation, registration toggle, session listing/revocation, login-event filters, and daily sign-in chart. Event timestamps and daily grouping use the viewing admin's selected timezone, including ET daylight-saving changes. Render the chart with dependency-free HTML/CSS.

- [x] **Step 1: Write UI tests** for hiding the page from non-admin roles; pending approval/denial; account role/status controls; clear duplicate errors; password reset without displaying stored secrets; active-session controls; and date/account/role filters for login events and daily counts.
- [x] **Step 2: Run `node --test tests/test_user_management_page.mjs`** and confirm the admin page and access behavior are missing.
- [x] **Step 3: Implement the users feature page and components.** Keep destructive actions behind explicit confirmation and show login counts from persisted events, not sessions.
- [x] **Step 4: Run `node --test tests/test_user_management_page.mjs`** and confirm all admin-page cases pass.
- [x] **Step 5: Commit** as `feat: add admin user management page`.

### Task 9: Architecture guidance and complete regression verification

**Files:**
- Create: `docs/architecture.md`, `docs/adding-features.md`
- Modify: `README.md`, `.env.example`, `requirements-dev.txt`
- Test: all Python and Node test files

**Interfaces:**
- Consumes: the implemented module boundaries and configuration from Tasks 1-8.
- Produces: setup/migration notes for `BD_INITIAL_ADMIN_USERNAME`, roles, pending registration, backup location, login history limits, Total Balance privacy, and a repeatable guide for adding a feature page/API/capability. Explain how to point `BD_DATABASE_PATH` at an existing database file before first startup.

- [x] **Step 1: Update the README and architecture guides** with the final paths, one-database model, one-time `BD_INITIAL_ADMIN_USERNAME` setup, registration approval, role permissions, backup location, login-history limits, Total Balance summary boundary, and per-account UTC/ET behavior.
- [x] **Step 2: Run `python -m unittest discover -s tests -p 'test_*.py' -v` and `node --test tests/*.mjs`** and resolve failures.
- [x] **Step 3: Run the application against a temporary fresh database and a copied legacy database.** Confirm fresh bootstrap works, legacy migration emits a backup, and `/api/health`, auth bootstrap, role-based balance access, and the Total Balance route work end to end.
- [x] **Step 4: Run `git diff --check` and verify runtime configuration reads only approved `BD_*` names** and visible app branding uses BD.
- [x] **Step 5: Commit** as `docs: document workspaces and feature modules`.

Sandbox verification note: all 51 Python tests passed through a temporary in-process ASGI test adapter because this execution environment's AnyIO background-thread bridge stalled even with an empty FastAPI app. The normal FastAPI `TestClient` tests remain unchanged. The Node suite passed normally; fresh and copied-legacy database smoke checks passed through the ASGI app.
