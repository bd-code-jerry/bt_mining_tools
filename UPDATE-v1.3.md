# Update to BD Mining Tools v1.3

This package contains application source that can be copied over your existing `bt_mining_tools` project. It contains no live database, `.env`, backups, or virtual environment.

## Install over your existing project

1. Stop the running dashboard. Close its terminal or stop the process/service you use to run it.
2. Make a separate backup of the project and its actual SQLite database. The default is `data/bd_dashboard.db`; if `.env` sets `BD_DATABASE_PATH`, back up that configured file instead. Stop the server before copying it.
3. Extract the ZIP into a temporary folder. Copy its contents into your existing project folder, where `run.py`, `backend`, and `frontend` already live. Accept replacement of the code files. Keep the existing project folder; do not place the update inside an extra nested folder.
4. Keep your existing `.env`, `data`, configured database, and `.venv`. The ZIP does not replace them. No new runtime dependency is required. If dependencies are missing, run `setup-windows.bat` or `setup-linux.sh`.
5. Start as before: `start-windows.bat` on Windows, or `bash start-linux.sh` on Linux. New migrations apply automatically. The migration runner makes a pre-upgrade SQLite backup beside the database in `backups`.
6. Open the dashboard and press **Ctrl+F5** to refresh JavaScript and styles. Sign in with your existing account.

API workspaces keep their existing rules: admins can choose any workspace, members read shared balances, and users manage their own private balances. Users administration remains admin-only.

## What is new

- **Overview** is the default page and displays allocated spending for each person.
- **Used** tracks sent money, received money, manual costs, and remaining balance: received funds minus recorded costs.
- Both pages support user, category, and date filters. Selecting a parent includes subcategories. Reports use saved manual expenses independently of Subnet 67 API usage.
- **Add cost** saves amount, date, category/purpose, optional note, and selected people. A $100 expense shared by two people saves $50 each. Where whole cents cannot divide equally, the earliest participant IDs receive the remaining cents.
- Categories can stand alone or contain subcategories. Add categories from the cost form; admins can rename, reorganize, or archive them. Old expense purposes remain recorded.
- **67 API keys** means **Subnet 67's API keys** and expands to API key balances and Total Balance.
- **API key balances** separates ordinary Balance History from Added Balance History, which shows prior balance, addition, and resulting balance with the provider's own unit.
- Choose **Light, Dark, Sand, Forest, or Midnight**; the browser remembers your choice.

## Existing API history

Earlier versions stored additions and ordinary balance updates in the same snapshot format. They did not store the addition amount or entry kind. This update preserves those rows and labels them **Legacy / unclassified** instead of guessing top-ups.

New Add Balance records automatically appear in Added Balance History. Authorized editors can classify old entries by entering their actual additions. Classification requires zero usage, nonnegative prior balances, and prior balance plus addition equal to resulting balance. Ordinary or unknown rows stay in Balance History.

Top-up edits use date and addition amounts; deletion follows the existing balance-history behavior. Controls remain limited to authorized API workspaces.

## Ledger permissions and reports

All active signed-in accounts can read the shared expense ledger. Admins can create and correct any ledger record; users can create records and correct their own; members read reports. Admins and users can add categories; admins manage existing categories. Active registered accounts, including admins, are selectable participants. Disabled/deleted accounts retain their previous allocated history.

Ledger ranges are **All time**, **1 Day**, **1 Week**, **1 Month** (30 days), and **Custom**. Presets end on today in your selected UTC/ET timezone; custom dates include both endpoints. API usage keeps its original latest-saved-date behavior. Report filters do not change the all-time funding/remaining-balance cards.

## If an upgrade fails

Keep the error message and backup files. To return to the old installation, stop the dashboard and restore both the previous source and your separate pre-upgrade database backup. Do not run two app versions against one live database.

## Developer checks

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
```
