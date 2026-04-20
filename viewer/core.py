"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Shared runtime, logging, and UI constants for the CCTV viewer.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv


def resolve_runtime_base_dir(
    *,
    frozen: bool | None = None,
    executable_path: str | None = None,
    script_path: str | None = None,
) -> Path:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(executable_path or sys.executable).resolve().parent
    return Path(script_path or __file__).resolve().parent.parent


def build_restart_argv(
    *,
    frozen: bool | None = None,
    executable_path: str | None = None,
    script_path: str | None = None,
    argv: list[str] | None = None,
) -> tuple[str, ...]:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    current_argv = list(sys.argv if argv is None else argv)
    extra_args = tuple(current_argv[1:])
    executable = str(Path(executable_path or sys.executable).resolve())
    if frozen:
        return (executable, *extra_args)
    # Default script path remains RTSP_viewer.py for source launches.
    default_script_path = Path(script_path or "RTSP_viewer.py").resolve()
    return (executable, str(default_script_path), *extra_args)


def launch_restart_process(args: tuple[str, ...], cwd: Path | None = None) -> None:
    launch_cwd = cwd or resolve_runtime_base_dir()
    subprocess.Popen(
        list(args),
        cwd=str(launch_cwd),
        close_fds=True,
    )


BASE_DIR = resolve_runtime_base_dir()
SETTINGS_PATH = BASE_DIR / "settings.json"
ENV_PATH = BASE_DIR / ".env"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

load_dotenv(dotenv_path=ENV_PATH)
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_EFFECTIVE_LOG_LEVEL = getattr(logging, LOG_LEVEL, logging.INFO)


class SecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        secrets = [os.getenv("UN", ""), os.getenv("PW", "")]
        for secret in secrets:
            if secret:
                message = message.replace(secret, "***")
        record.msg = message
        record.args = ()
        return True


logging.basicConfig(
    level=_EFFECTIVE_LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("rtsp-viewer")
log.addFilter(SecretsFilter())

APP_TITLE = "CCTV Viewer"
DEFAULT_RTSP_PORT = "554"
DEFAULT_NUM_CAMS = 16
DEFAULT_ROWS = 3
DEFAULT_COLS = 3
DEFAULT_UI_HIDE_MS = 2000
DEFAULT_RECONNECT_DELAY_MS = 2500
DEFAULT_MAX_RECONNECT_ATTEMPTS = 4
DEFAULT_OFFLINE_RETRY_MS = 60000
DEFAULT_RTSP_SCHEME = "rtsp"
MAX_RECONNECT_DELAY_MS = 30000
RECONNECT_JITTER_MAX_MS = 1000
FRAME_STALL_SECONDS = 10.0
DRIFT_THRESHOLD_MS = 2500
DRIFT_MIN_SAMPLES = 3
DRIFT_STRIKES_TO_RESYNC = 3
DRIFT_RESYNC_COOLDOWN_SECONDS = 30.0

GRID_SUBTYPE = 1
FOCUS_SUBTYPE = 0

BG = "#000000"
PANEL = "#0c1016"
CARD = "#111821"
CARD_HOVER = "#182230"
BORDER = "#171f2b"
BORDER_ACTIVE = "#28a8ff"
TEXT = "#ffffff"
TEXT_DIM = "#9ca3af"
LIVE = "#ff2600"
WARN = "#f59e0b"
ERROR = "#FF5100"

FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_CAM = ("Segoe UI", 9, "bold")
FONT_SMALL = ("Segoe UI", 8)

PAD = 1
