# Expense Ledger Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement and review the tasks below. The user approved all requirements and explicitly requested executable overwrite-ready code; proceed through delivery without another approval gate.

**Goal:** Deliver the approved team ledger, filtered reports, separate API top-up history, and themes as an overwrite-ready source ZIP.

**Architecture:** Keep FastAPI feature services/repositories and SQLite migrations. Share a report component across Overview and Used; keep Subnet 67 records workspace-scoped and independent of manual expenses. Work in the isolated feature branch.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, vanilla JavaScript modules/CSS, unittest and Node test runner.

**Spec:** `docs/superpowers/specs/2026-10-13-expense-ledger-design.md`

## Global constraints

- Preserve users, sessions, existing API workspaces, provider precision/units, `.env`, and the live database.
- Manual USD amounts use integer cents and equal persisted allocations.
- API history/usage never supplies Overview/Used expense totals.
- Existing saved Light/Dark preferences remain valid; add Sand, Forest, and Midnight.
- Only repository code and new migrations enter the overwrite ZIP; exclude `.env`, databases, backups, virtual environments, and git metadata.

## Review focus

- Deleted accounts and renamed/archived categories retain financial identity and purpose.
- Duplicate retries with a different payload cannot silently mutate an existing expense.
- Participant/category/date filters agree between totals and paginated rows.
- Direct requests cannot bypass existing private-workspace authorization.
- Legacy API snapshots never become invented top-up amounts.

## Shared ledger API contract

All endpoints are authenticated under `/api/expenses`. Money returned by the ledger is integer cents. POST/PUT accepts decimal-string `amount`, date strings, and the IDs below. Return validation errors through existing FastAPI patterns.

| Endpoint | Contract |
| --- | --- |
| GET `/participants` | `{participants:[{id,user_id,username,role,status,eligible}]}`; stable ledger participant IDs. |
| GET `/categories` | `{categories:[{id,name,parent_id,path,archived,effective_archived}]}`; include archived for history filters. |
| POST `/categories` | `{name,parent_id:null-or-id}` -> `{category:...}`. |
| PATCH `/categories/{id}` | `{name?,parent_id?,archived?}`; admin-only changes -> `{category:...}`. |
| GET `/summary` | `{origin_cents,received_cents,spent_cents,remaining_cents}`; all-time team ledger. |
| GET `/people` | Query `q,category_id,period,start_date,end_date`; `{people:[{id,username,role,status,total_cents}],total_cents,start_date,end_date}`. |
| GET `/costs` | Query `participant_id,q,category_id,period,start_date,end_date,page,page_size`; `{costs:[{id,amount_cents,allocated_cents,expense_date,category_id,category_path,note,created_by,can_edit,allocations:[{participant_id,username,share_cents}]}],pagination,filtered_total_cents,start_date,end_date}`. `allocated_cents` and filtered total sum only matching shares when filtering people, otherwise full costs. |
| POST `/costs` | `{amount,expense_date,category_id,note,participant_ids,request_id}` -> `{cost:...}`. |
| PUT `/costs/{id}` | Same financial fields (request_id optional); preserve identity; own records for user, any for admin -> `{cost:...}`. |
| DELETE `/costs/{id}` | Same edit permission -> `{ok:true}`. |
| GET `/transfers` | Query `kind,page,page_size`; `{transfers:[{id,kind,amount_cents,transfer_date,note,created_by,can_edit}],pagination}`. |
| POST `/transfers` | `{kind,amount,transfer_date,note,request_id}` -> `{transfer:...}`. |
| PUT/DELETE `/transfers/{id}` | Same own/admin correction rules; PUT accepts transfer fields. |

Periods are `all`, `day`, `week`, `month`, `custom`; dates inclusive; presets end on today in the actor's selected timezone and cover 1/7/30 days. Pagination uses `{page,page_size,total_items,total_pages}`. `q` searches usernames case-insensitively. Category filtering includes descendants. Admin/user can create ledger records/categories; member reads only. Admin/user write capability is `expenses:write`; all roles get `expenses:read`; category edits use `expenses:manage` for admin only. Services enforce creator ownership separately.

### Task 1: Ledger backend

**Files:** Create `backend/app/features/expenses/{__init__,router,schemas,service,repository}.py`, focused helper modules if useful, `backend/app/migrations/versions/v004_expense_ledger.py`, `tests/test_expenses.py`.
**Interfaces:** Implements the shared contract above. Root registers router/migration/capabilities; do not edit those shared files.
- [ ] Write API regression tests: $100/2 saves 5000 each; $100/3 saves 3334/3333/3333; parent VPS filters descendants; combined user/date/category totals match history; deactivated/deleted users keep old shares; archived category paths persist; retries deduplicate and conflicting payloads return 409; ownership rules reject forged edits; migrations preserve legacy API values.
- [ ] Run focused unittest tests and confirm the missing feature causes failure.
- [ ] Implement precise Decimal parsing, eligibility validation inside a transaction, durable participants, category trees/archive checks, snapshots, idempotent inserts, paginated reports and corrections.
- [ ] Run `.venv/bin/python -m unittest tests.test_expenses -v`; report evidence and any failures elsewhere.

### Task 2: API history separation

**Files:** Modify `backend/app/features/balances/{router,schemas,service,repository}.py`, `frontend/js/features/balances/{page,api}.js`, history components, `frontend/styles/balances.css`; create `backend/app/migrations/versions/v005_balance_additions.py`, `tests/test_balance_additions.py`, Node additions tests. Root registers migration.
**Interfaces:** Extend `/api/balances/overview` with `topup_history` and `topup_pagination`; query `topup_page,topup_page_size`. Keep `history`/`pagination` for ordinary/legacy rows; latest includes both types. Return `entry_kind` and per-provider `added_balance,balance_before`. New top-ups are explicitly tagged. Dedicated PUT `/api/balances/add-balance/{id}` accepts date/additions for edits and explicit legacy classification.
- [ ] Write failing tests for typed top-up data, separate pagination, no invented legacy amounts, classification validation, edits/deletes and forged workspaces.
- [ ] Verify RED with Python/Node focused commands.
- [ ] Implement v5 metadata, type-aware queries/mutations, separate history cards and tailored edit/classify controls. Keep existing API usage panels and workspace switching.
- [ ] Verify GREEN with focused tests and existing balance/workspace suites.

### Task 3: Overview/Used frontend

**Files:** Create `frontend/js/features/expenses/` API, state/format/report/form components; create `frontend/js/features/{overview,used}/page.js`, `frontend/styles/expenses.css`, `tests/test_expense_pages.mjs`.
**Interfaces:** Export `renderOverviewPage(container,options)` and `renderUsedPage(container,options)`. Consume the shared ledger contract. The navigation worker imports these functions and links the stylesheet.
- [ ] Write failing tests for per-person totals on both pages, AND filters, category paths, exact share preview, Add cost fields, saved refresh, preserved drafts when adding a category, escaping, and ignored stale responses.
- [ ] Verify RED with `node --test tests/test_expense_pages.mjs`.
- [ ] Implement fully usable pages with common person/category/date reports, selected-person history, pagination, Add cost/category, category administration, transfer forms/history, and authorized edit/delete. Use inline errors, confirmations, disabled save, request IDs, and current timezone callbacks.
- [ ] Verify GREEN with Node tests. Do not add empty placeholder controls.

### Task 4: Navigation and themes

**Files:** Modify `frontend/js/app/{pageRegistry,router}.js`, `frontend/js/app.js`, `frontend/js/shared/components/{sidebar,themeToggle}.js`, `frontend/js/theme.js`, `frontend/index.html`, `frontend/styles/{base,layout,auth}.css`, relevant theme/auth/registry tests.
**Interfaces:** Default protected route `overview`; registry imports Task 3 exports. Collapsible Subnet 67 group keeps API route hashes. Appearance catalog IDs `light,dark,sand,forest,midnight` maps each to native light/dark scheme and uses `bd-dashboard-theme`.
- [ ] Write failing tests for new default/registry visibility, group expansion, all presets/restoration, invalid or blocked storage, and synchronized controls after rerender.
- [ ] Verify RED with focused Node tests.
- [ ] Implement accessible grouped navigation and theme selector, early restoration, CSS token overrides and readable responsive controls; preserve existing role gating.
- [ ] Verify GREEN with relevant Node tests.

### Task 5: Integration, review and overwrite package

**Files:** Root modifies `backend/app/api.py`, `backend/app/core/permissions.py`, `backend/app/migrations/runner.py`, migration test version expectations, `README.md`, `UPDATE-v1.3.md`.
**Interfaces:** Register tasks 1/2 modules and migrations in order v1-v5. Review all tasks against approved spec and exercise a real app with temporary data.
- [ ] Register capabilities/router/migrations before backend tests, without changing old workspace rules.
- [ ] Independently review task changes and fix important findings before delivery.
- [ ] Run both full suites, `git diff --check`, and meaningful fresh/upgrade/restart/UI smoke checks.
- [ ] Create overwrite instructions: stop app, back up actual configured database, extract source into project root, preserve `.env`/data, run existing setup if necessary, restart for migrations, browser hard-refresh. Explain legacy top-up classification.
- [ ] Create and verify ZIP with top-level project contents ready to copy, excluding live configuration/data/env/git. Include manifest and validation counts. Upload the single deliverable and return its clickable link.
