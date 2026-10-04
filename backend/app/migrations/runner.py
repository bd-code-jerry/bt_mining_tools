from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .versions import v001_base_schema, v002_roles_workspaces, v003_timezone_preference

MIGRATIONS = (
    v001_base_schema,
    v002_roles_workspaces,
    v003_timezone_preference,
)
LEGACY_BASE_TABLES = {"users", "sessions", "providers", "history_entries", "history_values"}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if not str(row[0]).startswith("sqlite_")
    }


def _migration_rows(conn: sqlite3.Connection) -> dict[int, str]:
    if "schema_migrations" not in _table_names(conn):
        return {}
    return {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT version, name FROM schema_migrations")
    }


def _create_backup(conn: sqlite3.Connection, database_path: Path) -> Path:
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"{database_path.name}.{stamp}.pre-migration.sqlite3"
    with sqlite3.connect(backup_path) as backup_conn:
        conn.backup(backup_conn)
    return backup_path


def _validate_initial_admin(
    conn: sqlite3.Connection,
    *,
    initial_admin_username: str | None,
) -> None:
    if "users" not in _table_names(conn):
        return
    user_count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    if user_count == 0:
        return
    if not initial_admin_username or not initial_admin_username.strip():
        raise RuntimeError(
            "Set BD_INITIAL_ADMIN_USERNAME to an existing account before migrating this database."
        )
    match = conn.execute(
        "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
        (initial_admin_username.strip(),),
    ).fetchone()
    if match is None:
        raise RuntimeError(
            "BD_INITIAL_ADMIN_USERNAME must match an existing username; no database changes were made."
        )


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )"""
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _record_existing_base_schema(conn: sqlite3.Connection) -> None:
    rows = _migration_rows(conn)
    if rows:
        return
    tables = _table_names(conn)
    if not tables.intersection(LEGACY_BASE_TABLES):
        return
    if not LEGACY_BASE_TABLES.issubset(tables):
        missing = ", ".join(sorted(LEGACY_BASE_TABLES - tables))
        raise RuntimeError(f"Legacy database is missing base tables: {missing}.")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (1, "base_schema", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def migrate_database(
    database_path: Path,
    *,
    initial_admin_username: str | None,
) -> None:
    path = Path(database_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        tables_before = _table_names(conn)
        existing_application_db = bool(tables_before.intersection(LEGACY_BASE_TABLES))
        current_rows = _migration_rows(conn)
        current_version = max(current_rows, default=0)
        latest_version = MIGRATIONS[-1].VERSION

        if existing_application_db and current_version < 2:
            try:
                _validate_initial_admin(
                    conn,
                    initial_admin_username=initial_admin_username,
                )
            except RuntimeError as exc:
                raise RuntimeError(f"Database migration v2 required for {path}: {exc}") from exc

        if existing_application_db and current_version < latest_version:
            _create_backup(conn, path)

        _ensure_migration_table(conn)
        _record_existing_base_schema(conn)
        applied = _migration_rows(conn)

        for migration in MIGRATIONS:
            if migration.VERSION in applied:
                continue
            foreign_keys_disabled = migration.VERSION == 2
            if foreign_keys_disabled:
                conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.execute("BEGIN IMMEDIATE")
                migration.apply(conn, initial_admin_username=initial_admin_username)
                if foreign_keys_disabled:
                    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                    if violations:
                        raise RuntimeError("foreign-key validation found invalid rows.")
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (
                        migration.VERSION,
                        migration.NAME,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise RuntimeError(
                    f"Database migration v{migration.VERSION} ({migration.NAME}) failed for {path}: {exc}"
                ) from exc
            finally:
                if foreign_keys_disabled:
                    conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()
