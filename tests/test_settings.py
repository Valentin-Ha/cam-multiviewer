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

    def test_atomic_save_excludes_sensitive_connection_fields(self):
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
                self.assertNotIn("ip", stored)
                self.assertNotIn("port", stored)
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

    def test_resolve_runtime_base_dir_prefers_executable_when_frozen(self):
        base = RTSP_viewer.resolve_runtime_base_dir(
            frozen=True,
            executable_path=r"C:\bundle\CCTV-Viewer.exe",
            script_path=r"C:\src\RTSP_viewer.py",
        )
        self.assertEqual(base, Path(r"C:\bundle"))

    def test_build_restart_argv_source_and_frozen(self):
        source_args = RTSP_viewer.build_restart_argv(
            frozen=False,
            executable_path=r"C:\Python\python.exe",
            script_path=r"C:\repo\RTSP_viewer.py",
            argv=["RTSP_viewer.py", "--demo"],
        )
        self.assertEqual(source_args[0], str(Path(r"C:\Python\python.exe").resolve()))
        self.assertEqual(source_args[1], str(Path(r"C:\repo\RTSP_viewer.py").resolve()))
        self.assertEqual(source_args[2:], ("--demo",))

        frozen_args = RTSP_viewer.build_restart_argv(
            frozen=True,
            executable_path=r"C:\bundle\CCTV-Viewer.exe",
            argv=["CCTV-Viewer.exe", "--demo"],
        )
        self.assertEqual(frozen_args[0], str(Path(r"C:\bundle\CCTV-Viewer.exe").resolve()))
        self.assertEqual(frozen_args[1:], ("--demo",))

    def test_from_sources_leaves_missing_credentials_empty_without_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            env_path = Path(temp_dir) / ".env"
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
                        "start_fullscreen": True,
                    }
                ),
                encoding="utf-8",
            )

            original_settings_path = RTSP_viewer.SETTINGS_PATH
            original_env_path = RTSP_viewer.ENV_PATH
            try:
                RTSP_viewer.SETTINGS_PATH = settings_path
                RTSP_viewer.ENV_PATH = env_path
                with patch.dict(os.environ, {"UN": "", "PW": "", "IP": "", "PORT": ""}, clear=False):
                    with patch.object(RTSP_viewer.AppSettings, "bootstrap_missing_config") as bootstrap:
                        loaded = RTSP_viewer.AppSettings.from_sources()
                        self.assertEqual(loaded.username, "")
                        self.assertEqual(loaded.password, "")
                        self.assertEqual(loaded.ip, "")
                        self.assertEqual(loaded.port, RTSP_viewer.DEFAULT_RTSP_PORT)
                        bootstrap.assert_not_called()
            finally:
                RTSP_viewer.SETTINGS_PATH = original_settings_path
                RTSP_viewer.ENV_PATH = original_env_path

    def test_from_sources_defaults_port_to_standard_rtsp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "missing_settings.json"
            original_path = RTSP_viewer.SETTINGS_PATH
            try:
                RTSP_viewer.SETTINGS_PATH = settings_path
                with patch.dict(
                    os.environ,
                    {"UN": "env_user", "PW": "env_pass", "IP": "127.0.0.1", "PORT": ""},
                    clear=False,
                ):
                    loaded = RTSP_viewer.AppSettings.from_sources()
                    self.assertEqual(loaded.port, RTSP_viewer.DEFAULT_RTSP_PORT)
                    self.assertEqual(loaded.port, "554")
            finally:
                RTSP_viewer.SETTINGS_PATH = original_path

    def test_from_sources_malformed_numeric_settings_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "ip": "127.0.0.1",
                        "port": "8554",
                        "num_cams": "not-a-number",
                        "rows": "bad",
                        "cols": "bad",
                        "ui_hide_ms": "bad",
                        "reconnect_delay_ms": "bad",
                        "max_reconnect_attempts": "bad",
                        "offline_retry_ms": "bad",
                        "start_fullscreen": True,
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
                    self.assertEqual(loaded.num_cams, RTSP_viewer.DEFAULT_NUM_CAMS)
                    self.assertEqual(loaded.rows, RTSP_viewer.DEFAULT_ROWS)
                    self.assertEqual(loaded.cols, RTSP_viewer.DEFAULT_COLS)
                    self.assertEqual(loaded.ui_hide_ms, RTSP_viewer.DEFAULT_UI_HIDE_MS)
                    self.assertEqual(loaded.reconnect_delay_ms, RTSP_viewer.DEFAULT_RECONNECT_DELAY_MS)
                    self.assertEqual(loaded.max_reconnect_attempts, RTSP_viewer.DEFAULT_MAX_RECONNECT_ATTEMPTS)
                    self.assertEqual(loaded.offline_retry_ms, RTSP_viewer.DEFAULT_OFFLINE_RETRY_MS)
            finally:
                RTSP_viewer.SETTINGS_PATH = original_path

    def test_launch_restart_process_uses_expected_command_and_cwd(self):
        args = (
            r"C:\bundle\CCTV-Viewer.exe",
            "--demo",
        )
        with patch("RTSP_viewer.subprocess.Popen") as popen:
            RTSP_viewer.launch_restart_process(args, cwd=Path(r"C:\bundle"))
            popen.assert_called_once_with(
                [r"C:\bundle\CCTV-Viewer.exe", "--demo"],
                cwd=r"C:\bundle",
                close_fds=True,
            )

    def test_restart_application_launches_and_exits(self):
        class DummyApp:
            def __init__(self):
                self.closed = False
                self.root = None

            def close(self):
                self.closed = True

        app = DummyApp()
        restart_args = (r"C:\bundle\CCTV-Viewer.exe", "--demo")

        with patch("RTSP_viewer.build_restart_argv", return_value=restart_args):
            with patch("RTSP_viewer.launch_restart_process") as launcher:
                with patch("RTSP_viewer.sys.exit") as exit_mock:
                    RTSP_viewer.CCTVApp.restart_application(app)
                    launcher.assert_called_once_with(restart_args)
                    self.assertTrue(app.closed)
                    exit_mock.assert_called_once_with(0)

    def test_open_connection_settings_persists_pending_ui_edits(self):
        class DummyVar:
            def __init__(self, value):
                self._value = value

            def get(self):
                return self._value

        class DummyApp:
            def __init__(self):
                self.settings = None

        class SavedSettings:
            def __init__(self):
                self.saved = False

            def save(self):
                self.saved = True

        dialog = RTSP_viewer.SettingsDialog.__new__(RTSP_viewer.SettingsDialog)
        dialog.app = DummyApp()
        dialog.vars = {
            "num_cams": DummyVar("9"),
            "rows": DummyVar("3"),
            "cols": DummyVar("3"),
            "ui_hide_ms": DummyVar("1500"),
            "reconnect_delay_ms": DummyVar("500"),
            "max_reconnect_attempts": DummyVar("5"),
            "offline_retry_ms": DummyVar("60000"),
            "start_fullscreen": DummyVar(True),
        }

        saved_settings = SavedSettings()
        with patch("RTSP_viewer.AppSettings.from_form", return_value=saved_settings) as from_form:
            with patch("RTSP_viewer.ConnectionSettingsDialog") as connection_dialog:
                RTSP_viewer.SettingsDialog.open_connection_settings(dialog)

        from_form.assert_called_once()
        self.assertTrue(saved_settings.saved)
        self.assertIs(dialog.app.settings, saved_settings)
        connection_dialog.assert_called_once_with(dialog.app, parent=dialog)


if __name__ == "__main__":
    unittest.main()