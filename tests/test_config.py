from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def load_settings(self, extra_env: dict[str, str]) -> dict[str, object]:
        env = os.environ.copy()
        for key in list(env):
            if key.startswith(("BD_", "RSG_")):
                env.pop(key)
        env.update(extra_env)
        code = (
            "import json; from backend.app import config; "
            "print(json.dumps({'host': config.APP_HOST, 'port': config.APP_PORT, "
            "'registration_code': config.REGISTRATION_CODE, 'database_path': str(config.DATABASE_PATH), "
            "'initial_admin': getattr(config, 'INITIAL_ADMIN_USERNAME', None)}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_runtime_uses_bd_settings_and_ignores_rsg_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "bd.sqlite3")
            settings = self.load_settings(
                {
                    "RSG_HOST": "0.0.0.0",
                    "RSG_PORT": "9999",
                    "RSG_REGISTRATION_CODE": "legacy-code",
                    "RSG_DATABASE_PATH": str(Path(temp_dir) / "legacy.sqlite3"),
                    "BD_HOST": "127.0.0.1",
                    "BD_PORT": "8765",
                    "BD_DATABASE_PATH": database_path,
                }
            )
        self.assertEqual(settings["host"], "127.0.0.1")
        self.assertEqual(settings["port"], 8765)
        self.assertEqual(settings["registration_code"], "")
        self.assertEqual(settings["database_path"], database_path)
        self.assertIsNone(settings["initial_admin"])

    def test_nonlocal_bind_requires_bd_registration_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            for key in list(env):
                if key.startswith(("BD_", "RSG_")):
                    env.pop(key)
            env.update(
                {
                    "BD_HOST": "0.0.0.0",
                    "BD_REGISTRATION_CODE": "",
                    "BD_DATABASE_PATH": str(Path(temp_dir) / "config.sqlite3"),
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", "import backend.app.config"],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BD_REGISTRATION_CODE", result.stderr)


if __name__ == "__main__":
    unittest.main()
