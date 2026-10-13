# Team expense ledger and navigation

**Status:** Approved for implementation and overwrite-package delivery
**Date:** 2026-10-13

## Purpose and agreed scope

Extend the existing BD dashboard with saved team expenses, equal allocations to registered people, and per-person spending totals and reports on both Overview and Used. Group the existing API balance pages under an expandable **67 API keys** sidebar item. The number 67 identifies Bittensor Subnet 67; it is not the number of keys or providers. API provider history and usage do not appear in Overview or Used expense reports. The user's later API-history requirement adds a separate Added Balance History table on API key balances; API records belong on the Subnet 67 pages.

The user approved the proposed page layout and added these requirements: the purpose of an expense is a user-managed category, each category can optionally contain its own subcategories, and both Overview and Used allow searching/filtering by users and categories. The examples are API key and VPS. Categories describe manual expenses; selecting API key does not import or display Subnet 67 provider balance-history usage.

The user also requested more selectable appearance themes and preservation of the old project's workspace behavior. This means the existing repository's role-based API workspaces and authorizations remain in place.

## Navigation and pages

| Sidebar item | Behavior |
| --- | --- |
| Overview | Default page after sign-in. Show total allocated spending for every user/member, filter by person and category, and open individual usage history. |
| Used | Origin and Received totals with dated transactions, remaining balance, expense entry, total allocated spending for every user/member, and individual history. Filter expense reports by person and category. |
| 67 API keys | Subnet 67's API balance tracker. Expand/collapse group containing separate API key balances and Total Balance links. Initially collapsed; direct navigation to a child opens the group. |
| Users | Existing administrator account-management page, with its current authorization. |

Overview, Used, and the API group are available to all signed-in roles. Users retains its current admin-only visibility, as described in the proposed design. API child routes remain compatible with existing hashes. The group is keyboard-operable and exposes expanded state to assistive technologies.

## Existing API workspaces and separate added-balance history

Preserve the current API workspace model:

| Role | API workspace access |
| --- | --- |
| Admin | Select and read/edit any shared or private workspace. |
| Member | Read the shared workspace; no balance writes. |
| User | Read/edit that user's private workspace. |

Total Balance keeps the existing aggregate-only access across workspaces for all roles. Expense reports do not broaden access to private provider histories. Workspace selection, default resolution, and stale-workspace request handling remain unchanged.

On **API key balances**, show two clearly separated history sections:

| Section | Records and columns |
| --- | --- |
| Balance History | Ordinary balance updates using the existing date, Total, Used, and Left display. Rows imported from existing installations are labelled Legacy / unclassified. |
| Added Balance History | Explicit top-ups, with Date, API provider, Balance before, Amount added, Balance after, and provider unit. |

Each section has its own pagination and empty state. New top-ups appear only in Added Balance History, avoiding duplicate display in Balance History. A top-up affecting multiple providers lists the positive additions with their corresponding before/after values; unmodified providers are not shown as additions. USD, credits, and other units retain their own labels and are not summed together. API usage summaries remain scoped to their existing authorized API pages and are never included in Overview or Used expense totals.

Add Balance still applies the addition to the latest authorized workspace balance in one transaction, and a top-up contributes zero API usage. Store an explicit entry kind and per-provider added/before amounts, rather than trying to infer them from a snapshot later. A current balance snapshot is still saved for the existing latest-balance and aggregate calculations. Existing precision beyond two decimal places is preserved for provider balances; this is separate from cent-based manual USD expenses.

The current schema cannot reliably identify old top-ups or their added amounts. Upgrade preserves every old row and labels it Legacy / unclassified, without assigning invented additions. Authorized editors can explicitly classify a legacy entry as a top-up by supplying actual per-provider amounts. Validation requires nonnegative previous amounts, zero usage, and a consistent before-plus-added-equals-after relationship. Unknown old records remain in Balance History until classified.

Top-up correction uses amount/date controls tailored to this entry kind, keeping snapshot and addition metadata consistent. Generic history edits cannot silently invalidate top-up metadata. Deleting an authorized top-up removes its associated snapshot and metadata under existing history-deletion behavior. Neither correction nor deletion grants access to another workspace.

## Selectable themes

Add an appearance selector shared by the signed-in sidebar, sign-in page, and registration page. Proposed initial choices are:

| Theme | Appearance |
| --- | --- |
| Light | Existing light appearance. |
| Dark | Existing dark appearance. |
| Sand | Warm light backgrounds with restrained brown/gold accents. |
| Forest | Dark green backgrounds and green accents. |
| Midnight | Deep blue backgrounds and blue accents. |

Selecting a theme updates the whole app immediately, including forms, history tables, category controls, and dialogs. Preserve the existing browser preference key and saved Light/Dark values. Save the selected preset in that browser so it survives refresh, sign-out, and returning to the app. No account or workspace setting changes are needed.

Apply a valid saved preset before rendering the page to prevent an initial flash of another theme. Each preset maps to a native light or dark color scheme. Unknown saved values fall back to Light; storage failures do not prevent immediate switching. Use shared CSS variables, including affected hardcoded accent/sidebar colors, so every preset has readable text, status colors, active links, and focus states. The labeled selector is keyboard-operable and fits mobile layouts. Theme selection does not change records or the active workspace.

## Funding and remaining balance

The ledger is shared by the team, independent of private API workspaces.

- **Origin** records money sent: positive USD amount, transfer date, and optional note. Its card shows the all-time total sent and its table shows each transfer.
- **Received** records money actually received using the same fields. Its card shows the all-time total received and its table shows each receipt.
- **Cost / Remaining balance** is `total received - total recorded expenses`.
- **Total recorded costs** is displayed separately so the remaining-balance calculation is understandable.

Origin and Received may describe the same funding movement. Only Received funds the remaining balance; Origin is not added again. This formula is the assumption stated in the approved proposal. A negative remaining balance is displayed rather than silently rejecting a historical expense.

Both transfer kinds have entry controls and persistent, paginated histories. Financial amounts are stored as integer cents, with positive amounts and at most two decimal places validated on the server. Dates are ISO calendar dates and never shift when account timezone changes.

## Categories and optional subcategories

Categories form a tree: each has a name and either no parent or one parent category. A category may have zero or more children, including further descendants. Examples:

| Category | Optional subcategory |
| --- | --- |
| API key | OpenAI, OpenRouter, Chutes |
| VPS | Hetzner, DigitalOcean |
| Other | None required |

The examples are illustrative rather than provider integrations or automatically created records. Category management allows creating a top-level category or a child under an existing category, renaming a category, and archiving a category that should no longer be offered for new costs. Archived categories and their descendants remain visible in old expense records but are unavailable for new selection. Names are trimmed and unique without regard to case within the same parent. Empty names and cyclic parent assignments are rejected.

Add cost uses **Category / Purpose** as a required selector, with paths such as `API key / OpenAI` to distinguish children. Users can select a standalone category, a parent itself, or any active descendant. A subcategory is never mandatory merely because one exists. A nearby **Add category** control can create a category without leaving the form. No selection is made silently when the catalog is empty.

An optional note may explain a particular purchase. The selected category ID and its full path at save time are stored on the expense, preserving the original purpose when categories are renamed or archived. New expenses use current category names. Expense history shows category path and note separately.

## Expense entry and allocation

**Add cost** reveals a form containing:

1. Total USD amount.
2. Expense date.
3. Required category/purpose and optional note.
4. **Who is using it**, a checkbox list of active registered accounts with role labels and a Select all control.

Admin, member, and user accounts share the existing users table. Pending and disabled registrations are not offered for new allocations. Administrators are also selectable people. At least one distinct participant is required. The server checks participant eligibility at save time and rejects duplicate or invalid IDs.

Split the expense in integer cents over selected participants ordered by stable participant ID. The first participants receive any remainder cents, so shares differ by at most one cent and always sum to the full expense. `$100 / 2` saves `$50` each; `$100 / 3` saves `$33.34`, `$33.33`, and `$33.33`. Show the calculated shares before saving. Save the expense and all shares in one transaction. Changes in registrations never recalculate previous allocations.

Disable submit while saving and use a request identifier to make retries of the same submission return the saved record rather than duplicate it. Validate malformed dates, non-positive amounts, excessive precision, missing categories, archived categories, and missing participants with clear form errors.

## Usage reports on Overview and Used

Each person's usage is the sum of their saved expense allocations, including only manual ledger expenses. Both Overview and Used show a person-by-person table with username, role, and total spending. Every active user/member is included, with zero totals when there are no matching expenses; active admins can also appear as selected participants. Historical participants remain discoverable when their account is disabled or deleted, with their status identified.

Both pages provide username search, a searchable category selector, and date-range controls. Users can filter by person only, category only, or both together. Name search matches usernames without regard to case. Category selection matches the selected category and every descendant: selecting VPS includes expenses saved under VPS itself and, for example, VPS / Hetzner. Selecting a leaf matches only that category. Archived categories remain available as history filters. The category selector supports finding current category paths and saved historical paths without changing recorded purposes.

Person, category, and date criteria are combined with AND. Per-person totals and individual history apply all selected filters, so searching for one user and VPS shows only that person's allocated VPS spending for the chosen period. Default reports show all categories and all time. A clear/reset control restores these defaults. Filtering expense reports does not change the all-time Origin, Received, total recorded costs, or remaining-balance cards; these cards are labelled as team ledger totals.

Selecting a person opens their paginated history with expense date, saved category path, note, full expense amount, selected participants, and that person's allocated amount. The filtered total is computed across every matching allocation, independently of pagination. A team overview counts each full expense once; it does not count each participant's full expense again.

Range controls offer All time, 1 Day, 1 Week, 1 Month, and Custom. Presets end on today in the viewing account's selected timezone and cover 1, 7, or 30 inclusive calendar dates. Display resolved start and end dates. Custom endpoints are inclusive and reversed ranges are rejected. Filtering uses entered expense dates rather than record creation timestamps. Changing timezone refreshes preset bounds without changing saved dates. Ignore stale person/range responses when selections change quickly.

## Access rules

Use explicit expense capabilities, separately from balance-workspace capabilities. All active signed-in roles can read the shared ledger and person reports. The new participant endpoint exposes only IDs, names, roles, and eligibility/status needed by the feature, rather than admin account metadata.

Proposed write rules follow the existing editing roles: admins can create and correct any ledger record; users can create records and correct their own; members have read-only access. Admins and users can create categories; category renaming/archiving is admin-only. Existing Users administration and API workspace permissions remain authoritative. These are defaults for written-design review, since the original request did not specify new ledger mutation permissions.

All protected endpoints enforce capabilities and record ownership server-side. Client-submitted workspace IDs never grant ledger access. Disabled/pending accounts and unauthenticated requests cannot access it.

## Durable data and migration

Add version 4 for the ledger and a subsequent ordered migration for explicit API history kinds and per-provider top-up metadata through the existing transactional migration runner. Preserve existing accounts and API balance data and use its pre-upgrade backup behavior. Theme choices require no database migration.

| New table | Purpose |
| --- | --- |
| expense_participants | Stable identity, nullable link to an account, name snapshot; retained when an account is deleted. |
| expense_categories | Name, optional parent, archive flag, creator, timestamps. |
| expense_transfers | Origin/Received kind, integer amount, date, note, creator, request identifier, timestamps. |
| expense_costs | Integer total, date, category link and saved path, note, creator, request identifier, timestamps. |
| expense_allocations | Unique expense/participant pair and integer share amount. |

Creator/account references use nulling deletion rules. Expense participant identities and category records are not cascade-deleted when an account is removed. A new account reusing a deleted username receives a separate identity. Financial inserts and allocations are transactional; report queries use indexed dates and participant links. Corrections atomically replace allocation shares and refresh totals, subject to ownership checks.

## Implementation boundaries

Add `backend/app/features/expenses/` with router, schemas, service, and repository modules, and register it in `backend/app/api.py`. Add the ledger migration and capabilities. Routes cover participants, categories, transfer histories, expense creation/correction, summaries, and per-person paginated history. Extend the existing balances feature and a separate ordered migration for entry kind, top-up metadata, separate history queries/pagination, and validated top-up corrections/classification.

Add `frontend/js/features/overview/` and `frontend/js/features/used/`, with a shared expense API client and focused form/report components. Share the person-total table and user/category/date report controls between both pages so their filtering and totals are consistent. Update the page registry, sidebar, signed-in default routes, stylesheet links, and responsive styles. Reuse existing timezone, toast, and escaping utilities.

Extend API key balances with separate Balance History and Added Balance History components and type-aware editing. Preserve the existing authorized provider balance, usage, and aggregate functionality within the Subnet 67 pages. Existing provider snapshots are not converted into manual expense allocations. Extend `frontend/js/theme.js`, the shared appearance control, the startup theme allowlist in `frontend/index.html`, and CSS theme variables for all proposed presets.

## Verification and acceptance

Backend coverage must prove persistence across restart; exact two-person and uneven-cent splits; atomic failed saves; retry deduplication; eligible participant checks; category creation, optional nesting, case-insensitive sibling uniqueness and archival; historical purpose preservation; account deletion preservation; combined person/category/date filtering, parent-category descendant matching, and pagination-independent totals; remaining-balance math; and direct unauthorized mutation attempts.

API history coverage must prove separate ordinary/top-up pagination, accurate stored added and before/after amounts, no usage charged for additions, multiple provider units, high-precision additions, atomic updates, metadata-consistent corrections, deletion, honest legacy migration and explicit classification, unchanged aggregate/latest calculations, and current member/private/admin workspace authorization including forged workspace IDs.

Frontend coverage must prove Overview as the signed-in default, grouped sidebar expansion with 67 identifying the subnet, role visibility, Add cost revealing the required fields, optional subcategory selection, adding a category without losing a draft, Select all and preview shares, saved records/totals refreshing, per-user/member spending tables on both pages, combined person/category/date filters and reset behavior, escaping names/category notes, stale-response handling, absence of imported API history/usage from Overview and Used, and two distinct history sections on API key balances with separate page state.

Theme coverage must prove every preset's selection, persistence, valid light/dark native color scheme, early startup restoration, invalid-preference fallback, blocked-storage behavior, and selector synchronization after shell/auth rerenders. Inspect new pages and history sections in every theme at desktop and mobile widths.

Run the repository Python and Node suites and `git diff --check`. Inspect the resulting desktop/mobile pages in both themes when a runnable browser surface is available. At inspection time, the existing 42 Node tests passed; backend test execution was blocked by missing FastAPI in this environment. Dependency installation and implementation follow written-design review.
