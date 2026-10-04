from __future__ import annotations

import os
from ipaddress import ip_address
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(PROJECT_ROOT / ".env")


def _setting(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else value


def _database_setting(project_root: Path, bd_value: str | None) -> str:
    if bd_value is not None:
        return bd_value
    return "data/bd_dashboard.db"


APP_HOST = _setting("BD_HOST", "127.0.0.1")
APP_PORT = int(_setting("BD_PORT", "8765"))
REGISTRATION_CODE = _setting("BD_REGISTRATION_CODE", "").strip()
INITIAL_ADMIN_USERNAME = _setting("BD_INITIAL_ADMIN_USERNAME", "").strip() or None
SESSION_DAYS = max(1, int(_setting("BD_SESSION_DAYS", "14")))
COOKIE_SECURE = _setting("BD_COOKIE_SECURE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SESSION_COOKIE_NAME = "bd_session"


def validate_host_registration(host: str, registration_code: str) -> None:
    normalized_host = host.strip().lower()
    if normalized_host == "localhost":
        return
    try:
        is_loopback = ip_address(normalized_host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback and not registration_code.strip():
        raise RuntimeError(
            "Set BD_REGISTRATION_CODE before binding BD_HOST to a non-local interface."
        )


validate_host_registration(APP_HOST, REGISTRATION_CODE)

_db_value = _database_setting(PROJECT_ROOT, os.getenv("BD_DATABASE_PATH"))
_db_path = Path(_db_value)
if not _db_path.is_absolute():
    _db_path = PROJECT_ROOT / _db_path
DATABASE_PATH = _db_path.resolve()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
