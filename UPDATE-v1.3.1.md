# Fix missing Overview / Used after updating

v1.3.1 fixes update loading: every stylesheet and JavaScript module now loads from a versioned path, including lazy page imports. Responses prevent reuse of old HTML, modules, and account permissions. The runtime version is visible at `/api/health`; the terminal prints the version and project folder. An incomplete update now produces a clear warning rather than silently hiding Overview and Used.

## Install

1. Stop the dashboard with **Ctrl+C** in its running terminal. Back up the configured database as described in `UPDATE-v1.3.md`.
2. Copy **all contents** of this ZIP over your existing project folder, where `run.py`, `backend`, and `frontend` live. Choose replacement of files. Keep `.env`, `data`, and `.venv`; none are included in the ZIP.
3. Run `start-windows.bat` from that same folder. The terminal should say **BD Mining Tools v1.3.1** and print that project's location.
4. Open this fresh URL instead of leaving the old page open:

   `http://127.0.0.1:8765/?v=1.3.1#/overview`

   If you access another computer or a different port, use that server's address with `/?v=1.3.1#/overview`.

5. Sign in if needed. Overview, Used, and 67 API keys should appear; Users remains admin-only.

## Confirm the running files

From PowerShell:

```powershell
(Invoke-RestMethod "http://127.0.0.1:8765/api/health").version
```

Expected: **1.3.1**. The browser's module URLs should now begin with `/static/v1.3.1/`. New API balance overview requests include `topup_page` and `topup_page_size`.

If an incomplete-update warning appears, copy the full package again into the printed project folder and restart. This update makes no additional database schema change and retains all v1.3 expense, category, history, theme, and workspace behavior.
