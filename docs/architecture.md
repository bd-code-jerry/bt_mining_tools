# Architecture and data model

BD API Key Balances is a single-server application. FastAPI serves the API and the static frontend; SQLite stores accounts, sessions, workspaces, provider metadata, balance history, login events, and account preferences in one database file.

## Main code areas

| Area | Location | Responsibility |
| --- | --- | --- |
| Runtime configuration and database access | `backend/app/core/` | Read `BD_*` settings, open SQLite connections, authenticate requests, and enforce capabilities. |
| Ordered schema changes | `backend/app/migrations/` | Apply versioned, transactional SQLite migrations before the app serves requests. |
| Backend features | `backend/app/features/<feature>/` | Keep each feature's router, request/response schemas, business logic, and SQL repository together. |
| API assembly | `backend/app/api.py` | Register the feature routers. |
| Frontend route catalog | `frontend/js/app/` | Parse hash routes and map page metadata to renderers and required capabilities. |
| Frontend features | `frontend/js/features/<feature>/` | Keep each page, API client, and feature-specific components together. |
| Shared frontend code | `frontend/js/shared/` | Reuse the API client, shell, theme, timezone selector, modal, toast, and formatters. |
| Tests | `tests/` | Exercise backend behavior with Python `unittest` and frontend modules with Node's test runner. |

The frontend calls the API with a same-origin HTTP-only session cookie. The backend returns the signed-in account's role and capabilities; the frontend uses capabilities to display pages, while the backend checks capabilities and workspace access for every protected operation.

## One database and workspace access

Set `BD_DATABASE_PATH` to choose the SQLite file. The default is `data/bd_dashboard.db`; relative paths are resolved from the project folder. One database contains:

- One shared workspace for admin and member balance history.
- A private workspace for each user account. Its balance history is visible to that account and admins only.
- Provider definitions, balance snapshots, account records, sessions, login events, and per-account timezone preferences.

| Role | Balance history | Balance changes | Other features |
| --- | --- | --- | --- |
| `admin` | Any workspace | Any workspace | Manage accounts, approval, roles, sessions, and login reports. |
| `member` | Shared workspace | No | Read shared balances and aggregate Total Balance. |
| `user` | Their own private workspace | Their own workspace | Read aggregate Total Balance. |

All signed-in roles can read `/api/total-balances/summary`. It returns each workspace's current total, left balance, and cumulative spend, plus provider totals across the team. Provider units remain separate. The endpoint returns no dated entries, detailed history, or edit operations, so access to it does not grant access to another workspace's balance history.

All signed-in roles can choose UTC or Eastern Time (ET) for their account. The stored values are `UTC` and `America/New_York`; Eastern Time follows daylight-saving changes. Session and login-event timestamps are stored in UTC. Admin login-event display and daily grouping use the admin's selected timezone. Balance entry dates are date-only and do not change with timezone selection.

## Registration and account lifecycle

On an empty database, the first successful registration becomes the active admin. Every later self-registration remains pending and receives no session until an admin approves or denies it. An admin can also create an active account directly, change roles, disable or re-enable accounts, reset passwords, revoke sessions, and delete accounts. Usernames and email addresses are unique without regard to letter case.

Successful sign-ins create login events independently of active sessions. Logging out or revoking a session does not erase its login event. The admin login-event endpoint returns at most 500 recent matching events; a daily report is limited to 367 calendar days. Events do not store IP addresses or session tokens.

## Configuration

Copy `.env.example` to `.env`. Runtime settings use `BD_*` names:

| Setting | Default | Use |
| --- | --- | --- |
| `BD_HOST` | `127.0.0.1` | Interface to bind. Non-local interfaces require a registration code. |
| `BD_PORT` | `8765` | HTTP port. |
| `BD_REGISTRATION_CODE` | empty | Registration code. It must be set before binding to a non-local interface. |
| `BD_SESSION_DAYS` | `14` | Session lifetime. |
| `BD_COOKIE_SECURE` | `false` | Set `true` when the app is served through HTTPS. |
| `BD_DATABASE_PATH` | `data/bd_dashboard.db` | The one SQLite database file. |
| `BD_INITIAL_ADMIN_USERNAME` | empty | One-time selection of an existing account to promote during a legacy database migration. |

## Using an existing database

To continue using an existing **BD dashboard** database, stop the running server and make a separate copy of the database file first. Set `BD_DATABASE_PATH` to that file's absolute path in `.env` before starting this version. If it is left unset or points somewhere else, the app initializes the default database instead and will appear to have no previous accounts or balances.

When upgrading a pre-workspace database that contains users, set `BD_INITIAL_ADMIN_USERNAME` to the username of an existing account before startup. The match is case-insensitive. That account becomes admin; other existing accounts become active members. Existing accounts receive no email addresses, and old sessions remain in the database. No login events are inferred from old sessions.

The migration runner validates the selected username before making changes, then creates a SQLite backup using SQLite's backup API before applying schema changes. The backup is saved next to the database in a `backups/` directory with a `.pre-migration.sqlite3` suffix. For the default database, this is `data/backups/`. Remove `BD_INITIAL_ADMIN_USERNAME` after the first successful migration. Do not point multiple app versions at the same live database during migration.

`BD_INITIAL_ADMIN_USERNAME` is only for migrating the previous BD dashboard schema. The app does not automatically import unrelated products' database formats; export or transform those records into the dashboard schema first.

## Startup and verification

The Windows setup/start scripts are `setup-windows.bat` and `start-windows.bat`; the Linux scripts are `setup-linux.sh` and `start-linux.sh`. The app applies pending migrations at startup, seeds missing provider catalog entries, and exposes `GET /api/health` for a health check.

From the project root, install development dependencies and run the regression suites:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
```
