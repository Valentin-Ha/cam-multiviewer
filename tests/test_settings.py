"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import RTSP_viewer


class SettingsTests(unittest.TestCase):
    def test_parse_bool(self):
        self.assertTrue(RTSP_viewer.parse_bool("true"))
        self.assertTrue(RTSP_viewer.parse_bool("YES"))
        self.assertFalse(RTSP_viewer.parse_bool("false"))
        self.assertFalse(RTSP_viewer.parse_bool("0"))
        self.assertTrue(RTSP_viewer.parse_bool(True))
        self.assertFalse(RTSP_viewer.parse_bool(None, default=False))

    def test_validate_host_rejects_invalid(self):
        with self.assertRaises(RuntimeError):
            RTSP_viewer.validate_host("not a real host name !!!")

    def test_atomic_save_excludes_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            original_path = RTSP_viewer.SETTINGS_PATH
            try:
                RTSP_viewer.SETTINGS_PATH = settings_path
                settings = RTSP_viewer.AppSettings(
                    username="admin",
                    password="secret",
                    ip="127.0.0.1",
                    port="8554",
                    num_cams=4,
                    rows=2,
                    cols=2,
                    ui_hide_ms=1000,
                    reconnect_delay_ms=500,
                    max_reconnect_attempts=3,
                    offline_retry_ms=60000,
                    start_fullscreen=True,
                )
                settings.save()
                stored = json.loads(settings_path.read_text(encoding="utf-8"))
                self.assertNotIn("username", stored)
                self.assertNotIn("password", stored)
                self.assertEqual(stored["ip"], "127.0.0.1")
            finally:
                RTSP_viewer.SETTINGS_PATH = original_path

    def test_from_sources_uses_env_for_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "ip": "127.0.0.1",
                        "port": "8554",
                        "num_cams": 9,
                        "rows": 3,
                        "cols": 3,
                        "ui_hide_ms": 1000,
                        "reconnect_delay_ms": 500,
                        "max_reconnect_attempts": 4,
                        "offline_retry_ms": 60000,
                        "start_fullscreen": "false",
                    }
                ),
                encoding="utf-8",
            )
            original_path = RTSP_viewer.SETTINGS_PATH
            try:
                RTSP_viewer.SETTINGS_PATH = settings_path
                with patch.dict(
                    os.environ,
                    {"UN": "env_user", "PW": "env_pass", "IP": "127.0.0.1", "PORT": "8554"},
                    clear=False,
                ):
                    loaded = RTSP_viewer.AppSettings.from_sources()
                    self.assertEqual(loaded.username, "env_user")
                    self.assertEqual(loaded.password, "env_pass")
                    self.assertFalse(loaded.start_fullscreen)
            finally:
                RTSP_viewer.SETTINGS_PATH = original_path


if __name__ == "__main__":
    unittest.main()
