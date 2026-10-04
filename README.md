# BD API Key Balances Dashboard

A small team dashboard for manually tracking API-provider balances and usage.

The current build includes:

- **API keys balances** — workspace-scoped balances, usage ranges, and editable history.
- **Total Balance** — current total, remaining balance, and cumulative spend by provider and workspace, with an overall team summary.
- **User management** — admin approval, account roles/status, sessions, and timezone-aware login activity.
- **Login / Register** — accounts stored in the server's single SQLite database; new registrations wait for admin approval.
- **Light / dark mode** and an account-level **UTC / Eastern Time (ET)** preference.

The frontend uses a page registry and feature folders. The backend groups routes, schemas, services, and repositories by feature. See [Architecture](docs/architecture.md) and [Adding a feature](docs/adding-features.md) before extending the project.

A fresh install starts with the provider catalog and no balance history. Add your own balances after creating an account. Existing database files keep their current history.

## Main behavior

### New Balance

The balance-entry form is hidden until you click **+ New Balance**.

For each API provider:

- **Total Balance** is the latest saved remaining balance and is read-only in this form.
- Enter **Used** and **Left** is calculated automatically.
- Enter **Left** and **Used** is calculated automatically.
- Inputs support more than two decimal places.
- Typing no longer rewrites the active field on every keystroke, so selecting the entire number and replacing it does not move the cursor to the end.

The relationship is:

```text
Total = Used + Left
```

If you click **Save to History** without changing any values, the latest remaining balances are saved again with `0` new usage.

The form checks whether the latest balance changed after it was opened. If another teammate saved first, this entry is rejected so the old form cannot overwrite newer balances.

### Add Balance

Click **+ Add Balance** when you buy/top up an API account. Enter only the amount added. The dashboard shows:

```text
New Total Balance = Current Balance + Added Balance
```

Saving creates a new balance snapshot. Added funds/credits are not counted as usage. The server performs the addition against the latest saved balance so a stale browser page does not overwrite a newer team update.

### Balance History

History has server-side pagination with selectable page sizes of 5, 10, 20 or 50 rows.

Each saved row has:

- **Edit** — correct the date, Total, Used or Left values.
- **Delete** — remove a wrong/unwanted history entry after a confirmation prompt.

Deleting a row also removes that row's usage from the cumulative totals.

### Total used balance

The large blue number is cumulative usage for providers whose unit is **USD**. Credits and Chutes `t` are not added to the dollar total because those units are not dollars. Their usage is tracked separately.

### Total used balance by API key and date range

The **Total Used Balance by API Key** section shows the summed `Used` value for every provider. It supports:

- **All Time** — every saved history entry.
- **1 Day** — the latest saved balance date.
- **1 Week** — the latest saved date plus the previous 6 calendar days.
- **1 Month** — the latest saved date plus the previous 29 calendar days.
- **Custom Range** — choose inclusive **From** and **To** dates with the calendar inputs, for example September 1 through September 20.

Preset ranges end on the latest saved history date rather than the computer clock. This means the buttons still show useful data if the most recent balance entry was backdated or no entry has been saved today.

Each API key keeps its own unit. USD, credits, and Chutes `t` are shown separately instead of being added together into a meaningless mixed-unit total.

### Total Balance

The **Total Balance** page shows the latest total and left balances plus cumulative spend for each provider. It shows each workspace and a team total, while keeping USD, credits, and other provider units separate. It exposes aggregate numbers only; it does not show another workspace's dated entries or detailed history.

### Accounts and workspaces

The first account registered in a fresh database becomes the admin. Later self-registrations stay pending and cannot sign in until an admin approves or denies them. An admin can also create active accounts directly.

| Role | Balance access |
| --- | --- |
| Admin | Read and edit balances in any workspace; manage accounts and sessions. |
| Member | Read-only access to the shared workspace. |
| User | Read and edit their own private workspace. |

All three roles can read the aggregate Total Balance page and change their own timezone. Login event timestamps and daily counts use the viewing admin's timezone. The stored choices are `UTC` and `America/New_York`; Eastern Time follows daylight-saving changes. Balance entry dates remain date-only values.

Login events are saved separately from live sessions, so signing out does not remove the login record. The login event list returns up to 500 recent matches, and a daily report can cover at most 367 calendar days.

### Light and dark appearance

Use the **Light mode / Dark mode** button on the sign-in and registration pages or in the sidebar after signing in. Your choice is saved in the current browser and is used the next time you open the dashboard.

## Folder structure

```text
bd-api-balances/
│
├── backend/app/
│   ├── core/                           # config, database, security, permissions
│   ├── features/
│   │   ├── auth/                       # sign-in, registration, sessions
│   │   ├── balances/                   # balance history and provider catalog
│   │   ├── preferences/                # account timezone
│   │   ├── total_balances/             # aggregate-only team summary
│   │   ├── usage/                      # date-range usage reports
│   │   ├── users/                      # admin account and login APIs
│   │   └── workspaces/                 # shared/private workspace access
│   ├── migrations/                     # ordered SQLite schema migrations
│   ├── api.py                          # registers feature routers
│   └── main.py                         # FastAPI app and static frontend
│
├── frontend/
│   ├── index.html
│   ├── styles/                         # base, layout, auth, balances, users, totals
│   └── js/
│       ├── app/                        # route parsing and page registry
│       ├── shared/                     # API client, shell components, utilities
│       ├── features/
│       │   ├── auth/
│       │   ├── balances/               # page, API, history component
│       │   ├── preferences/
│       │   ├── total-balances/
│       │   ├── usage/
│       │   ├── users/                  # page, API, account/activity components
│       │   └── workspaces/
│       ├── app.js
│       └── theme.js
│
├── docs/                               # architecture and extension guide
├── tests/                              # Python backend and Node frontend tests
│
├── data/
│   ├── bd_dashboard.db                # created automatically on first run
│   └── backups/                       # pre-migration SQLite backups
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── run.py
├── setup-windows.bat
├── start-windows.bat
├── setup-linux.sh
└── start-linux.sh
```

## Windows 11 setup

### 1. Extract the project

For example:

```text
D:\Projects\bd-api-balances
```

### 2. Run setup once

Double-click:

```text
setup-windows.bat
```

It creates `.venv`, installs the runtime requirements from `requirements.txt` **inside that virtual environment**, and creates `.env` from `.env.example`. This includes the timezone database package needed on Windows. The setup script uses any working Python 3.10+ installation already on the PC and uses `.venv\Scripts\python.exe` directly, so it does not depend on `activate.bat` or require Python 3.11 specifically.

If an earlier setup attempt left an incomplete `.venv`, run `setup-windows.bat` again. The corrected script removes the incomplete environment and rebuilds it.

### 3. Set a team registration code for network access

Open `.env` and set:

```text
BD_REGISTRATION_CODE=a-long-private-team-code
```

For local-only use, the code can remain blank. For LAN access, also set:

```text
BD_HOST=0.0.0.0
```

The server refuses to start on a non-local interface without a registration code. Only teammates who know that code can register.

### 4. Start the dashboard

Double-click:

```text
start-windows.bat
```

On the computer running the server, open:

```text
http://127.0.0.1:8765
```

On a fresh database, the first registration becomes the admin. Later registrations wait for approval. Sign in to approve them on the **Users** page.

For an existing dashboard database, see [Using an existing database](docs/architecture.md#using-an-existing-database) before starting the app. Set `BD_DATABASE_PATH` to the database file before the first startup so the app does not initialize a new default database.

## Let teammates use it from another PC on the same network

To allow LAN connections, set `BD_HOST=0.0.0.0` and a private `BD_REGISTRATION_CODE` in `.env`, then restart the server. By default it listens only on the host PC.

Another device can connect if Windows Firewall allows the port.

### 1. Find the host PC IPv4 address

On the host PC, open Command Prompt:

```bat
ipconfig
```

Look for an address similar to:

```text
192.168.1.50
```

### 2. Allow port 8765 through Windows Firewall

Open **PowerShell as Administrator** on the host PC:

```powershell
New-NetFirewallRule -DisplayName "BD Dashboard 8765" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
```

Use this on a trusted **Private** network, not an untrusted public Wi-Fi network.

### 3. Friend opens the dashboard

From the friend's computer on the same LAN/Wi-Fi:

```text
http://192.168.1.50:8765
```

Replace `192.168.1.50` with the actual IPv4 address of the computer running the dashboard.

Everyone signs in to the same server and database. Admins and members use shared balance history; users get a private workspace. All roles can see the aggregate Total Balance page. By default the database file is:

```text
data/bd_dashboard.db
```

Use the admin **Users** page to approve registrations and set each account to `admin`, `member`, or `user`.

## Access from outside your home/office network

Do **not** directly expose port 8765 to the public internet with router port forwarding.

For remote access, use one of these approaches instead:

- Tailscale between team computers.
- A VPS with HTTPS/reverse proxy.
- A secure tunnel/reverse proxy with HTTPS.

If you later run the dashboard behind HTTPS, set:

```text
BD_COOKIE_SECURE=true
```

## Where to edit things later

Each page lives in its frontend feature folder, for example `frontend/js/features/balances/` or `frontend/js/features/users/`. Backend endpoints and business logic live in the matching `backend/app/features/<feature>/` folder. Add page routes in `frontend/js/app/pageRegistry.js`; sidebar links are generated from that registry and the account's capabilities. Register backend routers in `backend/app/api.py`.

For a step-by-step example, see [Adding a feature](docs/adding-features.md).

### Change the API provider catalog

`backend/app/features/balances/provider_catalog.py` defines the initial provider catalog. It is added on startup when missing; sample balance history is not seeded.

The app does not seed sample balance history. Existing history remains in your database.

## Database backup

Stop the dashboard and copy this file somewhere safe:

```text
data/bd_dashboard.db
```

That single file contains accounts, sessions, workspaces, providers, balance history, login events, and preferences.

Before a legacy database is upgraded, the migration runner creates a SQLite backup in `data/backups/` (or beside the configured database file in its `backups/` subfolder). Keep independent backups as well. Stop the server before manually copying or replacing the live database.

## Run the integrity tests

Install the development dependencies once with `python -m pip install -r requirements-dev.txt`. Then run from the project folder:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
```
