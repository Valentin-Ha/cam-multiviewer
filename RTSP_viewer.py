"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Compatibility facade and entrypoint for the modularized CCTV Viewer.
"""

from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from viewer.app import RTSPViewerApp as _RTSPViewerApp
from viewer.core import (
    APP_TITLE,
    BASE_DIR,
    BG,
    BORDER,
    BORDER_ACTIVE,
    CARD,
    CARD_HOVER,
    DEFAULT_COLS,
    DEFAULT_MAX_RECONNECT_ATTEMPTS,
    DEFAULT_NUM_CAMS,
    DEFAULT_OFFLINE_RETRY_MS,
    DEFAULT_RECONNECT_DELAY_MS,
    DEFAULT_ROWS,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_SCHEME,
    DEFAULT_UI_HIDE_MS,
    DRIFT_MIN_SAMPLES,
    DRIFT_RESYNC_COOLDOWN_SECONDS,
    DRIFT_STRIKES_TO_RESYNC,
    DRIFT_THRESHOLD_MS,
    ENV_PATH,
    ERROR,
    FOCUS_SUBTYPE,
    FONT_CAM,
    FONT_SMALL,
    FONT_TITLE,
    FONT_UI,
    FRAME_STALL_SECONDS,
    GRID_SUBTYPE,
    LIVE,
    LOG_DIR,
    LOG_FILE,
    MAX_RECONNECT_DELAY_MS,
    PAD,
    PANEL,
    RECONNECT_JITTER_MAX_MS,
    SETTINGS_PATH,
    TEXT,
    TEXT_DIM,
    WARN,
    build_restart_argv,
    launch_restart_process,
    log,
    resolve_runtime_base_dir,
)
from viewer.settings import AppSettings, atomic_write_json, parse_bool, validate_host
from viewer.stream import CameraTile, compute_reconnect_delay_ms, create_vlc_instance, media_options, rtsp_url
from viewer.ui import ConnectionSettingsDialog as _ConnectionSettingsDialog
from viewer.ui import SettingsDialog as _SettingsDialog


class ConnectionSettingsDialog(_ConnectionSettingsDialog):
    """Compatibility alias for the extracted UI dialog class."""


class SettingsDialog(_SettingsDialog):
    """Compatibility wrapper that keeps patch targets on RTSP_viewer names."""

    def open_connection_settings(self) -> None:
        self.persist_pending_settings(show_error=False)
        ConnectionSettingsDialog(self.app, parent=self)


class CCTVApp:
    """Compatibility shim for tests targeting restart behavior only."""

    def restart_application(self) -> None:
        restart_args = build_restart_argv()
        try:
            launch_restart_process(restart_args)
        except Exception:
            log.exception("Failed to relaunch application")
            if getattr(self, "root", None) is not None:
                messagebox.showerror(
                    "Restart Failed",
                    "Could not restart the application. Please relaunch it manually.",
                    parent=self.root,
                )
            return
        self.close()
        sys.exit(0)


class RTSPViewerApp(_RTSPViewerApp):
    """Runtime app class wired to compatibility SettingsDialog export."""

    def open_settings(self) -> None:
        SettingsDialog(self)


if __name__ == "__main__":
    try:
        RTSPViewerApp().run()
    except Exception as exc:
        log.exception("Application failed to start")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Startup Error", str(exc), parent=root)
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
