# User Management and Workspace Architecture

**Status:** Draft for user review
**Date:** 2026-10-01

## 1. Purpose

Add role-based access, administrator user management, and isolated user workspaces to the BD dashboard. Reorganize the application around feature modules so future pages can be added without putting unrelated UI, API, and database logic into the same files.

The existing application is a FastAPI service with a vanilla JavaScript frontend and one SQLite database. Today, all authenticated accounts see and edit one shared balance history. This design keeps that history as the shared workspace and adds private workspaces for users assigned the `user` role.

## 2. Goals and scope

- Provide `admin`, `member`, and `user` roles with server-enforced permissions.
- Let admins manage accounts, registration, roles, account status, password resets, and active sessions.
- Keep current balance history available in a shared workspace without losing existing database content.
- Give each `user` a private workspace, with no access to another user's workspace.
- Add a read-only Total Balance page that shows each workspace's latest total and remaining balances, cumulative spend, and combined team totals to every signed-in role.
- Let every signed-in account choose UTC or Eastern Time (ET); persist the choice per account and use it when showing timestamps and login-day counts.
- Organize backend and frontend by feature, document how to add a future page, and keep the current UI framework dependency-free.
- Support future Dashboard, Settings, Wallets (coldkey/hotkey), and Tao State features through the same module and permission patterns.

The specific behavior of future Wallets, Tao State, and other planned pages is outside this implementation. This work supplies the module structure and permission extension points; it does not create empty or nonfunctional pages for those features.

## 3. Roles and workspace access

| Role | Workspace access | Actions |
| --- | --- | --- |
| `admin` | All shared and private workspaces | Read and edit balances in any workspace; manage accounts, registration, roles, status, passwords, and sessions. |
| `member` | Shared workspace details, plus aggregate Total Balance summaries for every workspace | Read shared dashboard, balance history, and usage data; cannot make changes or manage accounts. |
| `user` | That user's private workspace details, plus aggregate Total Balance summaries for every workspace | Read and manage balances and history in that workspace; cannot access the shared workspace or another user's detailed data. |

The server determines accessible workspaces from the authenticated user. A request-supplied workspace ID is never sufficient authorization. Admins can select a workspace through the UI; members always use the shared workspace; users always use their own workspace. The separately authorized Total Balance summary exposes only each workspace's username or shared-workspace label and aggregate balances; it does not grant access to another workspace's history or detailed records.

Every page and endpoint declares a named capability, such as `balances:read`, `balances:write`, `total_balances:read`, `users:manage`, or `wallets:manage`. `total_balances:read` is granted to all three roles. Backend checks are authoritative. The frontend uses the same capability names to decide which navigation items and controls to show. New capabilities are denied until explicitly granted.

Every signed-in account can change its own time zone between UTC and ET. The preference follows the account across devices and defaults to UTC for new and migrated accounts. Store the supported values as `UTC` and the IANA zone `America/New_York`; this makes ET display follow daylight saving time automatically. Store event timestamps in UTC. Display timestamps and group login events by day in the viewing admin's selected time zone. Balance entry dates are calendar dates rather than timestamps, so changing time zones never shifts a saved balance date. The signed-in shell exposes the selector to all roles; a future Settings page can host the same preference without changing its API.

## 4. Account registration and initial administrator

### Fresh database

- Self-registration starts enabled so an administrator can be created.
- The first successful registration is immediately active with the `admin` role, inside a serialized transaction. It signs the initial admin in, and that new session creates one login event. Simultaneous registrations cannot both become administrators.
- Every later self-registration creates a `pending` account request with no session and no workspace access. The applicant sees that approval is pending and cannot sign in.
- An admin reviews pending requests, approves one with an assigned role (`admin`, `member`, or `user`, defaulting to `member`), or denies it. Denial deletes the pending account record and releases its username and email.
- An admin can open or close self-registration from the user-management page. Closing it blocks public registrations but still lets an admin create an active account from that page.
- Admin-created accounts start active as `member`; the admin can assign another role. They require a unique username, email, and initial password.
- `BD_REGISTRATION_CODE` remains the deployment-level gate for public registration. The user's BD-only `config.py` settings remain authoritative; no `RSG_*` environment fallbacks are added.
- New accounts must provide an email address. Email is not verified or used for automatic password recovery; it is a unique sign-in identifier, and admins handle password resets.

### Existing database

- The migration reads `BD_INITIAL_ADMIN_USERNAME` from `.env`/the process environment.
- That existing account becomes the initial active administrator; all other existing accounts remain active as `member`.
- Existing accounts have no email or persistent last-login value in the current schema, so the migration leaves email and `last_login_at` blank. They can continue signing in with their username until an admin adds a unique email; last-login reporting starts with the next successful sign-in.
- If the setting is missing or does not match an account, startup stops with a clear error before applying the role migration. This prevents silently granting admin to the wrong account or leaving the operator locked out.
- After migration succeeds, the setting can be removed. Its effect is limited to the one-time migration.
- Existing accounts are not placed in the pending queue. Registration for new accounts remains enabled after migration until an admin closes it; later self-registrations are pending approval.

## 5. Account management and sessions

The admin user-management page lists username, email, role, account status, registration date, last login, and active sign-in sessions. It includes a pending-approval queue.

- Admins approve pending requests and assign the account's role. They can also deny and remove a pending request.
- Admins can assign `admin`, `member`, or `user` roles to active accounts. Only admins can change roles.
- Admins can add or change an account's email. Usernames and non-empty emails are unique case-insensitively. If either identifier is already in use by a pending, active, or disabled account, registration or account creation is rejected with a clear message; no duplicate account is created.
- Login accepts either username or email. Existing accounts with no email continue to use their username.
- Admins can disable and re-enable accounts. Disabling immediately revokes all sessions and prevents new sign-ins; re-enabling preserves the account and any private workspace.
- Admins can reset a password by setting a new password. Passwords remain one-way hashed; no endpoint or UI returns an existing password. A reset revokes the user's active sessions.
- Pending and disabled users cannot sign in, even if they have a previously issued session token.
- Each successful sign-in creates one durable login event and updates persistent `last_login_at` data. One sign-in (and new session) counts as one event; multiple sign-ins by the same account on one day count separately. Failed sign-ins are not counted. Admins can view a login-event table and a daily count chart, filter by date, account, or role, and view active sessions separately.
- A login event remains in the activity report after its session ends. It records the account, role at sign-in, and timestamp; it does not record passwords, session tokens, or IP addresses.
- Existing databases have no historical login-event table. The report starts counting successful logins after this migration; earlier sign-ins cannot be reconstructed. Existing unexpired sessions remain visible in the active-session list.
- Session rows include creation, last activity, and expiration timestamps; admins can revoke a single session or all sessions for an account.
- Logout, disable, password reset, and session revocation remove or invalidate the corresponding server-side session records without deleting the login event.
- The system refuses to disable, demote, or delete the last enabled administrator.

### Total Balance page

This read-only page is available to admins, members, and users. It shows one aggregate row for the shared workspace and each private user workspace, followed by combined team totals. Each row reports the latest recorded `total_balance`, latest `left_balance`, and cumulative `used_balance` across history for each provider. Totals are grouped by provider and unit so unlike currencies or credits are never added together. The page returns no dated history entries or edit controls; normal workspace authorization continues to protect those details.

## 6. Workspace lifecycle and deletion

- The database contains one shared workspace. The migration assigns all existing balance-history entries to it.
- A private workspace is created when an account is assigned the `user` role. Reassigning a `user` to `member` hides that workspace from the user but preserves it; an admin can still access it. Reassigning the account to `user` restores access to the same workspace.
- Each private workspace has one owner. Its history and usage summaries are filtered by workspace ID on every backend query.
- **Disable** preserves the user and workspace but blocks access.
- **Delete** permanently removes the user and that user's private workspace and history. It does not delete shared history. Existing foreign-key behavior keeps shared history while clearing attribution to a deleted account.
- Deletion is a confirmed admin action. The last enabled admin cannot be deleted.

## 7. Database and migration design

Use a single SQLite database at `BD_DATABASE_PATH`, defaulting to `data/bd_dashboard.db`. Keep migration code ordered and versioned under `backend/app/migrations/`; do not rely on `CREATE TABLE IF NOT EXISTS` alone for upgrades.

The migration adds or extends:

- `users`: username, email (nullable only for migrated accounts), role, account status (`pending`, `active`, or `disabled`), and last login timestamp. Username and non-empty email have case-insensitive unique constraints.
- `login_events`: one row per successful sign-in, including user ID, sign-in timestamp, and role at that time. Events remain after logout and are removed when the user is permanently deleted.
- `workspaces`: workspace kind (`shared` or `private`), owner, display name, and creation time.
- `history_entries`: required workspace foreign key and an index that supports workspace-scoped date pagination.
- `sessions`: last activity timestamp and existing expiry/revocation behavior.
- `app_settings`: persistent registration enabled/disabled state.
- `users.timezone`: per-account display time zone, restricted to `UTC` or `America/New_York`, defaulting to `UTC`.
- A schema-version table for applied migrations.

`providers` remain a shared catalog. The migration creates the shared workspace, assigns all existing history to it, adds roles to existing accounts according to Section 4, and preserves users, password hashes, provider records, and balance values. It must be transactional and safe to rerun.

The Total Balance summary is derived from existing balance records: for each workspace and provider, use the latest history row for `total_balance` and `left_balance`, and sum `used_balance` across that workspace's history for cumulative spend. Combine workspace rows into team totals by provider, preserving units. No private history entries are included in this response.

## 8. Backend organization and responsibilities

Backend modules are grouped by feature. Routers handle HTTP validation and response mapping; schemas define request and response shapes; services implement business rules and authorization; repositories contain SQL. Shared configuration, database connections, security primitives, and permission helpers live in `core/`.

```text
backend/app/
  core/
    config.py                 # BD environment and database settings
    database.py               # connection lifecycle and startup
    security.py               # password/session primitives
    dependencies.py           # authenticated-user dependency
    permissions.py            # role/capability checks
  features/
    auth/                     # username/email login, registration, approval state, logout
    users/                    # approvals, account management, login and session activity
    preferences/              # per-account UTC/ET preference
    workspaces/               # workspace listing and authorization context
    balances/                 # balance and history operations
    total_balances/            # role-visible per-workspace and team balance summaries
    usage/                    # workspace-scoped usage summaries
  migrations/
    runner.py                 # ordered migration runner
    versions/                 # individual schema/data migrations
  api.py                      # registers feature routers
  main.py                     # app setup, startup, static frontend
```

Each implemented backend feature contains:

```text
<feature>/
  router.py       # HTTP routes, input validation, and response mapping
  schemas.py      # request and response data shapes
  service.py      # business rules and permission-aware workflows
  repository.py   # SQL queries and persistence
```

Each feature owns its route, schemas, service, and repository files. Cross-feature SQL does not live in page routers. Every balance and usage query requires an authorized workspace context. The `total_balances` service may aggregate across workspaces only for the summary response and only for callers with `total_balances:read`; it must not return detailed history. User-administration endpoints require `users:manage`.

## 9. Frontend organization and page registration

The frontend stays vanilla JavaScript. A page registry owns route names, labels, render functions, and required capabilities. The app router handles bootstrap and route dispatch; shared UI components stay separate from feature pages.

```text
frontend/js/
  app/
    router.js                 # authentication bootstrap and route dispatch
    pageRegistry.js           # route, label, renderer, and capability
  shared/
    api/client.js             # fetch wrapper and shared error handling
    components/               # sidebar, theme toggle, modal, and toast
    utils/                    # shared formatting and helpers
  features/
    auth/                     # username/email login, register form, pending state
    users/                    # approval queue, account controls, login activity
    preferences/              # shared UTC/ET selector and preference API
    workspaces/               # admin workspace selector
    balances/                 # balances page, history components, and API calls
    total-balances/           # read-only per-user summary and team totals page
    usage/                    # usage summary UI and API calls
```

Each implemented frontend feature keeps its page renderer in `page.js`, feature-specific requests in `api.js`, and reusable feature UI in `components/`.

Future features can follow the same layout, for example `features/settings/`, `features/wallets/`, and `features/tao-state/`. Adding a page means adding its feature module, registering its route/navigation metadata and capability, adding a backend feature module if it needs data, and adding tests. A page hidden from navigation is not treated as protected; its backend endpoints still enforce permissions.

The auth feature provides username-or-email sign-in and pending-registration status. The users feature provides the approval queue, account list, login-event table and daily chart, and active-session controls. The preferences feature provides a shared timezone selector to every signed-in role and persists only that account's choice. The Total Balance page calls only the aggregate summary API and is registered for all roles; it does not reuse or broaden the detailed balance-history API.

Add `docs/architecture.md` to describe the top-level module boundaries and `docs/adding-features.md` as a short step-by-step guide to creating and registering a page, adding its backend API, declaring permissions, and writing feature tests.

## 10. Migration safety, error handling, and operational behavior

- Before applying a migration to an existing database, create a timestamped SQLite backup with SQLite's backup API. The app should emit the database path and migration version in startup errors without exposing passwords, session tokens, or secret material.
- If the initial admin username is invalid, stop with an actionable error and leave the pre-migration data intact.
- Invalid or unauthorized role/workspace actions return a clear `403`; missing resources return `404`; duplicate usernames or emails return `409`.
- The first admin cannot remove their own last-admin protection by editing the UI; the rule is enforced in the backend transaction.
- `BD_INITIAL_ADMIN_USERNAME` is read from configuration only for bootstrapping an existing database and is not exposed to browser JavaScript.

## 11. Tests and acceptance criteria

Backend tests cover:

- Fresh-database first-registration admin assignment, including simultaneous sign-ups.
- Existing-database migration, history preservation, explicit admin selection, invalid/missing bootstrap configuration, and repeat startup.
- Later registrations remain pending until approval, cannot sign in before approval, and create no session.
- Duplicate case-insensitive usernames/emails are rejected; username and email sign-in both work.
- A successful login creates one persistent event; session logout/revocation preserves the event; activity counts group by day, account, and role.
- Timezone preferences are per account, available to all roles, default to UTC, accept only UTC or ET, and drive displayed login timestamps and viewer-local daily grouping across daylight-saving transitions.
- Member read-only access to the shared workspace and denial of private workspaces.
- User access only to their own workspace, including API attempts with another workspace ID.
- Admin access and user/registration/session management.
- Total Balance summaries show each workspace and combined team totals to members and users, grouped by provider/unit, without exposing another workspace's history or edit operations.
- Password reset, account disable, and session revocation behavior.
- Last-enabled-admin protection and delete behavior for private versus shared history.
- Workspace-scoped pagination, latest balances, edits, deletes, and usage totals.

Frontend tests cover:

- Role-aware navigation and page registry behavior.
- Pending approval state, admin approval/denial controls, and duplicate-identifier errors.
- Login activity table, daily chart filters, active-session controls, and username-or-email login.
- Admin user list and actions, member read-only balance UI, and user workspace context.
- Workspace selector visibility for admins only.
- Total Balance navigation and summaries are available to all roles; the page displays per-workspace and combined totals and never loads detailed histories for other users.
- Sign-up enabled/disabled states and capability-based controls.
- The UTC/ET selector is available to admin, member, and user accounts; selection persists on the account, and saved balance calendar dates remain unchanged.

Acceptance criteria:

1. Existing data upgrades into a shared workspace without loss.
2. Server-side checks prevent cross-workspace access even when a caller modifies API parameters.
3. Members cannot mutate balances; users can mutate only their own; admins can manage all workspaces.
4. Admins can control registration and accounts without ever retrieving plaintext passwords.
5. New self-registrations cannot sign in until approved; duplicate usernames or emails are rejected.
6. Login events persist after logout and the admin daily chart agrees with event counts.
7. Account disable, deletion, role changes, password reset, and session revocation enforce the documented lifecycle rules.
8. Frontend/backend files have clear feature ownership and the feature-addition guide describes how to add a page and API safely.
9. Members and users can read per-workspace and team Total Balance summaries, while detailed balance histories remain limited to each role's authorized workspaces.
10. Existing light/dark mode, balance calculations, and startup behavior remain functional.
11. Every signed-in role can choose UTC or ET, the choice persists per account, login-day counts use the viewer's selected zone, and date-only balance entries are not shifted.

## 12. Review notes

This draft reflects the user-approved choices: one SQLite database; admins see all workspaces; members read the shared workspace; regular users have private workspaces; members and users can view aggregate Total Balance rows for every workspace; new registrations wait for admin approval; login accepts unique usernames or emails; duplicate identifiers are rejected while pending, active, or disabled and become available again after denial; admins can review login events and daily sign-in counts; every role can select a persistent UTC or ET time zone; `BD_INITIAL_ADMIN_USERNAME` selects the administrator when upgrading an existing database; password resets revoke sessions; disabling preserves data; deletion removes a private workspace; and the last enabled administrator is protected.
