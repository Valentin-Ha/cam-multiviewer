"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import socket
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from ipaddress import ip_address
from logging.handlers import RotatingFileHandler
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

import vlc
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"
ENV_PATH = BASE_DIR / ".env"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

load_dotenv(dotenv_path=ENV_PATH)
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_effective_log_level = getattr(logging, LOG_LEVEL, logging.INFO)


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
    level=_effective_log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("rtsp-viewer")
log.addFilter(SecretsFilter())

APP_TITLE = "RTSP Multi Stream Viewer"
DEFAULT_NUM_CAMS = 16
DEFAULT_ROWS = 3
DEFAULT_COLS = 3
DEFAULT_UI_HIDE_MS = 2000
DEFAULT_RECONNECT_DELAY_MS = 2500
DEFAULT_MAX_RECONNECT_ATTEMPTS = 4
DEFAULT_OFFLINE_RETRY_MS = 60000
MAX_RECONNECT_DELAY_MS = 30000
RECONNECT_JITTER_MAX_MS = 1000
RTSP_SCHEME = os.getenv("RTSP_SCHEME", "rtsp").strip().lower()
FRAME_STALL_SECONDS = 10.0
DRIFT_THRESHOLD_MS = 2500
DRIFT_MIN_SAMPLES = 3
DRIFT_STRIKES_TO_RESYNC = 3
DRIFT_RESYNC_COOLDOWN_SECONDS = 30.0

GRID_SUBTYPE = 1
FOCUS_SUBTYPE = 0

BG = "#05070b"
PANEL = "#0c1016"
CARD = "#111821"
CARD_HOVER = "#182230"
BORDER = "#171f2b"
BORDER_ACTIVE = "#28a8ff"
TEXT = "#f4f7fb"
TEXT_DIM = "#9ca3af"
LIVE = "#22c55e"
WARN = "#f59e0b"
ERROR = "#ef4444"

FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_CAM = ("Segoe UI", 9, "bold")
FONT_SMALL = ("Segoe UI", 8)

PAD = 1


def create_vlc_instance(quality: str) -> vlc.Instance:
    common = ["--rtsp-tcp", "--no-video-title-show", "--quiet"]
    if quality == "grid":
        options = common + [
            "--live-caching=100",
            "--network-caching=100",
            "--clock-jitter=0",
            "--clock-synchro=0",
            "--rtsp-frame-buffer-size=250000",
            "--drop-late-frames",
            "--skip-frames",
            "--avcodec-fast",
            "--avcodec-hurry-up",
        ]
    else:
        options = common + [
            "--network-caching=700",
            "--rtsp-frame-buffer-size=1000000",
        ]
    return vlc.Instance(*options)


def rtsp_url(settings: "AppSettings", channel: int, subtype: int) -> str:
    # Credentials are required by RTSP auth; never log this URL directly.
    scheme = "rtsps" if RTSP_SCHEME == "rtsps" else "rtsp"
    return (
        f"{scheme}://{settings.username}:{settings.password}@{settings.ip}:{settings.port}"
        f"/cam/realmonitor?channel={channel}&subtype={subtype}"
    )


def parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def validate_host(value: str) -> str:
    host = value.strip()
    if not host:
        raise RuntimeError("IP or host must not be empty")
    try:
        ip_address(host)
        return host
    except ValueError:
        pass
    try:
        socket.gethostbyname(host)
    except OSError as exc:
        raise RuntimeError(f"Invalid IP/host '{host}'") from exc
    return host


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    temp_fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def compute_reconnect_delay_ms(attempt: int, base_ms: int) -> int:
    growth = max(0, attempt - 1)
    core_delay = min(base_ms * (2**growth), MAX_RECONNECT_DELAY_MS)
    jitter = random.randint(0, RECONNECT_JITTER_MAX_MS)
    return core_delay + jitter


def media_options(quality: str) -> tuple[str, ...]:
    if quality == "grid":
        return (
            ":live-caching=100",
            ":network-caching=100",
            ":clock-jitter=0",
            ":clock-synchro=0",
            ":rtsp-frame-buffer-size=250000",
        )
    return (
        ":network-caching=700",
        ":rtsp-frame-buffer-size=1000000",
        ":avcodec-hw=dxva2",
    )


@dataclass
class AppSettings:
    username: str
    password: str
    ip: str
    port: str
    num_cams: int = DEFAULT_NUM_CAMS
    rows: int = DEFAULT_ROWS
    cols: int = DEFAULT_COLS
    ui_hide_ms: int = DEFAULT_UI_HIDE_MS
    reconnect_delay_ms: int = DEFAULT_RECONNECT_DELAY_MS
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS
    offline_retry_ms: int = DEFAULT_OFFLINE_RETRY_MS
    start_fullscreen: bool = True

    @property
    def page_size(self) -> int:
        return self.rows * self.cols

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(self.num_cams / self.page_size))

    @classmethod
    def from_sources(cls) -> "AppSettings":
        data = {
            "username": "",
            "password": "",
            "ip": "",
            "port": "8554",
            "num_cams": DEFAULT_NUM_CAMS,
            "rows": DEFAULT_ROWS,
            "cols": DEFAULT_COLS,
            "ui_hide_ms": DEFAULT_UI_HIDE_MS,
            "reconnect_delay_ms": DEFAULT_RECONNECT_DELAY_MS,
            "max_reconnect_attempts": DEFAULT_MAX_RECONNECT_ATTEMPTS,
            "offline_retry_ms": DEFAULT_OFFLINE_RETRY_MS,
            "start_fullscreen": True,
        }

        if SETTINGS_PATH.exists():
            try:
                stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    for key in (
                        "ip",
                        "port",
                        "num_cams",
                        "rows",
                        "cols",
                        "ui_hide_ms",
                        "reconnect_delay_ms",
                        "max_reconnect_attempts",
                        "offline_retry_ms",
                        "start_fullscreen",
                    ):
                        if key in stored:
                            data[key] = stored[key]
            except Exception:
                log.exception("Failed to load settings.json; using env/defaults")

        data["username"] = os.getenv("UN", "").strip()
        data["password"] = os.getenv("PW", "")
        data["ip"] = os.getenv("IP", str(data.get("ip", "")).strip())
        data["port"] = os.getenv("PORT", str(data.get("port", "8554")).strip())

        data["num_cams"] = int(data.get("num_cams", DEFAULT_NUM_CAMS))
        data["rows"] = int(data.get("rows", DEFAULT_ROWS))
        data["cols"] = int(data.get("cols", DEFAULT_COLS))
        data["ui_hide_ms"] = int(data.get("ui_hide_ms", DEFAULT_UI_HIDE_MS))
        data["reconnect_delay_ms"] = int(data.get("reconnect_delay_ms", DEFAULT_RECONNECT_DELAY_MS))
        data["max_reconnect_attempts"] = int(data.get("max_reconnect_attempts", DEFAULT_MAX_RECONNECT_ATTEMPTS))
        data["offline_retry_ms"] = int(data.get("offline_retry_ms", DEFAULT_OFFLINE_RETRY_MS))
        data["start_fullscreen"] = parse_bool(data.get("start_fullscreen", True), default=True)

        settings = cls(**data)
        settings.validate()
        if not SETTINGS_PATH.exists():
            settings.save()
        return settings

    @classmethod
    def from_form(cls, data: dict[str, object]) -> "AppSettings":
        username = os.getenv("UN", "").strip()
        password = os.getenv("PW", "")
        settings = cls(
            username=username,
            password=password,
            ip=str(data["ip"]).strip(),
            port=str(data["port"]).strip(),
            num_cams=int(data["num_cams"]),
            rows=int(data["rows"]),
            cols=int(data["cols"]),
            ui_hide_ms=int(data["ui_hide_ms"]),
            reconnect_delay_ms=int(data["reconnect_delay_ms"]),
            max_reconnect_attempts=int(data["max_reconnect_attempts"]),
            offline_retry_ms=int(data.get("offline_retry_ms", DEFAULT_OFFLINE_RETRY_MS)),
            start_fullscreen=parse_bool(data["start_fullscreen"], default=True),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not all([self.username, self.password, self.ip, self.port]):
            raise RuntimeError("Missing UN, PW, IP, or PORT in your .env or environment")
        self.ip = validate_host(self.ip)
        try:
            port_num = int(self.port)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("PORT must be a whole number") from exc
        if not (1 <= port_num <= 65535):
            raise RuntimeError("PORT must be between 1 and 65535")
        self.port = str(port_num)
        if self.num_cams < 1:
            raise RuntimeError("num_cams must be at least 1")
        if self.rows < 1 or self.cols < 1:
            raise RuntimeError("rows and cols must be at least 1")
        if self.ui_hide_ms < 250:
            raise RuntimeError("ui_hide_ms is too small")
        if self.reconnect_delay_ms < 250:
            raise RuntimeError("reconnect_delay_ms is too small")
        if self.max_reconnect_attempts < 1:
            raise RuntimeError("max_reconnect_attempts must be at least 1")
        if self.offline_retry_ms < 1000:
            raise RuntimeError("offline_retry_ms must be at least 1000")

    def save(self) -> None:
        payload = asdict(self)
        payload.pop("username", None)
        payload.pop("password", None)
        atomic_write_json(SETTINGS_PATH, payload)


class CameraTile:
    def __init__(self, app: "RTSPViewerApp", index: int):
        self.app = app
        self.index = index
        self.channel = index + 1
        self.active_player: vlc.MediaPlayer | None = None
        self.grid_player: vlc.MediaPlayer | None = None
        self.focus_player: vlc.MediaPlayer | None = None
        self.active_mode = "grid"
        self.started = False
        self.desired_active = False
        self.retry_attempts = 0
        self.retry_job = None
        self.offline_retry_job = None
        self.last_start_time = 0.0
        self.last_frame_progress_time = 0.0
        self.last_video_counter = -1
        self.audio_enabled = False
        self.chrome_visible = True
        self.status_key = "IDLE:text"
        self.drift_strikes = 0
        self.last_drift_resync_time = 0.0

        self.card = tk.Frame(app.grid_frame, bg=BORDER, bd=0, highlightthickness=0)
        self.inner = tk.Frame(self.card, bg=CARD, bd=0)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.header = tk.Frame(self.inner, bg=CARD, height=22)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        self.cam_label = tk.Label(
            self.header,
            text=f"CAM {self.channel:02d}",
            bg=CARD,
            fg=TEXT,
            font=FONT_CAM,
            padx=8,
            anchor="w",
            cursor="hand2",
        )
        self.cam_label.pack(side="left", fill="y")

        self.state_label = tk.Label(
            self.header,
            text="IDLE",
            bg=CARD,
            fg=TEXT_DIM,
            font=FONT_SMALL,
            padx=8,
            cursor="hand2",
        )
        self.state_label.pack(side="right", fill="y")

        self.video_host = tk.Frame(self.inner, bg="black")
        self.video_host.pack(fill="both", expand=True)

        self.bind_ui()

    def bind_ui(self) -> None:
        clickable = [self.card, self.inner, self.header, self.cam_label, self.state_label, self.video_host]
        for widget in clickable:
            widget.bind("<Button-1>", lambda _event, idx=self.index: self.app.toggle_focus(idx))

        hoverable = [self.card, self.inner, self.header, self.cam_label, self.state_label]
        for widget in hoverable:
            widget.bind("<Enter>", lambda _event, tile=self: tile.set_hover(True))
            widget.bind("<Leave>", lambda _event, tile=self: tile.set_hover(False))

    def set_hover(self, hovered: bool) -> None:
        if self.app.focused_index == self.index:
            return
        bg_card = CARD_HOVER if hovered else CARD
        border = BORDER_ACTIVE if hovered else BORDER
        self.card.configure(bg=border)
        self.inner.configure(bg=bg_card)
        self.header.configure(bg=bg_card)
        for widget in (self.cam_label, self.state_label):
            widget.configure(bg=bg_card)

    def set_active(self, active: bool) -> None:
        bg = CARD_HOVER if active else CARD
        border = BORDER_ACTIVE if active else BORDER
        self.card.configure(bg=border)
        self.inner.configure(bg=bg)
        self.header.configure(bg=bg)
        for widget in (self.cam_label, self.state_label):
            widget.configure(bg=bg)

    def set_status(self, text: str, color: str) -> None:
        key = f"{text}:{color}"
        if self.status_key == key:
            return
        self.status_key = key
        self.state_label.configure(text=text, fg=color)

    def set_chrome_visible(self, visible: bool) -> None:
        if self.chrome_visible == visible:
            return
        self.chrome_visible = visible
        if visible:
            self.header.pack(fill="x", side="top")
        else:
            self.header.pack_forget()

    def grid_at(self, row: int, col: int) -> None:
        self.card.grid(row=row, column=col, sticky="nsew", padx=PAD, pady=PAD)

    def hide(self) -> None:
        self.card.grid_forget()

    def destroy(self) -> None:
        self.cancel_reconnect()
        self.stop()
        self.card.destroy()

    def attach_player(self, player: vlc.MediaPlayer) -> None:
        self.app.root.update_idletasks()
        wid = self.video_host.winfo_id()
        if hasattr(player, "set_hwnd"):
            player.set_hwnd(wid)
        elif hasattr(player, "set_xwindow"):
            player.set_xwindow(wid)
        elif hasattr(player, "set_nsobject"):
            player.set_nsobject(wid)
        player.video_set_mouse_input(False)
        player.video_set_key_input(False)

    def player_for_mode(self, hd: bool) -> vlc.MediaPlayer:
        if hd:
            if self.focus_player is None:
                self.focus_player = self.app.focus_vlc_instance.media_player_new()
            return self.focus_player
        if self.grid_player is None:
            self.grid_player = self.app.grid_vlc_instance.media_player_new()
        return self.grid_player

    def build_media(self, hd: bool):
        instance = self.app.focus_vlc_instance if hd else self.app.grid_vlc_instance
        media = instance.media_new(rtsp_url(self.app.settings, self.channel, FOCUS_SUBTYPE if hd else GRID_SUBTYPE))
        for option in media_options("focus" if hd else "grid"):
            media.add_option(option)
        return media

    def _stop_other_player(self, hd: bool) -> None:
        other = self.grid_player if hd else self.focus_player
        if other is not None:
            try:
                other.stop()
            except Exception:
                log.exception("Failed to stop camera %s player", self.channel)

    def _apply_audio_state(self, muted: bool) -> None:
        if self.active_player is None:
            return
        try:
            self.active_player.audio_set_volume(100)
            self.active_player.audio_set_mute(muted)
        except Exception:
            log.exception("Failed to update audio state for camera %s", self.channel)

    def apply_audio_policy(self) -> None:
        self._apply_audio_state(muted=self.active_mode != "focus" or not self.audio_enabled)

    def set_audio_enabled(self, enabled: bool) -> None:
        self.audio_enabled = enabled
        if self.active_mode == "focus":
            self.apply_audio_policy()

    def _play(self, hd: bool, force: bool = False) -> None:
        self.cancel_reconnect()
        self.cancel_offline_retry()
        player = self.player_for_mode(hd)
        self._stop_other_player(hd)
        self.attach_player(player)
        try:
            player.set_media(self.build_media(hd))
            player.play()
        except Exception:
            log.exception("Failed to start stream for camera %s", self.channel)
            try:
                player.stop()
            except Exception:
                pass
            self.started = False
            self.desired_active = True
            self.active_player = None
            self.set_status("ERROR", ERROR)
            self.schedule_reconnect("player start failed")
            return

        self.started = True
        self.desired_active = True
        self.active_player = player
        self.active_mode = "focus" if hd else "grid"
        self.last_start_time = time.monotonic()
        self.last_frame_progress_time = self.last_start_time
        self.last_video_counter = -1
        if force:
            self.retry_attempts = 0
        self.apply_audio_policy()
        self.set_status("CONNECTING", BORDER_ACTIVE if hd else TEXT_DIM)
        log.info("Camera %s started in %s mode", self.channel, self.active_mode)

    def start(self) -> None:
        self.start_grid_stream(force=True)

    def start_grid_stream(self, force: bool = False) -> None:
        if not force and self.active_mode == "grid" and self.active_player is not None:
            self.resume()
            return
        self._play(False, force=force)

    def start_focus_stream(self, force: bool = False) -> None:
        if not force and self.active_mode == "focus" and self.active_player is not None:
            self.resume()
            return
        self._play(True, force=force)

    def switch_stream(self, hd: bool) -> None:
        if hd:
            self.start_focus_stream(force=True)
        else:
            self.start_grid_stream(force=True)

    def pause(self) -> None:
        if self.active_player is None:
            return
        try:
            self.active_player.pause()
            self.set_status("PAUSED", TEXT_DIM)
        except Exception:
            log.exception("Failed to pause camera %s", self.channel)

    def resume(self) -> None:
        if self.active_player is None:
            return
        try:
            self.active_player.play()
            self.apply_audio_policy()
            self.set_status("LIVE", LIVE)
        except Exception:
            log.exception("Failed to resume camera %s", self.channel)

    def restart_current_stream(self, force: bool = False) -> None:
        self.cancel_reconnect()
        if force:
            self.retry_attempts = 0
        if self.active_mode == "focus":
            self.start_focus_stream(force=True)
        else:
            self.start_grid_stream(force=True)

    def cancel_reconnect(self) -> None:
        if self.retry_job is not None:
            try:
                self.app.root.after_cancel(self.retry_job)
            except RuntimeError:
                pass
            self.retry_job = None

    def cancel_offline_retry(self) -> None:
        if self.offline_retry_job is not None:
            try:
                self.app.root.after_cancel(self.offline_retry_job)
            except RuntimeError:
                pass
            self.offline_retry_job = None

    def _schedule_offline_retry(self) -> None:
        if self.offline_retry_job is not None:
            return
        delay = self.app.settings.offline_retry_ms + (self.index * 150)
        self.set_status("OFFLINE", ERROR)
        log.warning("Camera %s entering offline retry mode; next retry in %sms", self.channel, delay)
        self.offline_retry_job = self.app.root.after(delay, self._do_offline_retry)

    def _do_offline_retry(self) -> None:
        self.offline_retry_job = None
        if not self.desired_active:
            return
        log.info("Offline retry for camera %s", self.channel)
        self.retry_attempts = 0
        self.restart_current_stream(force=True)

    def schedule_reconnect(self, reason: str) -> None:
        if not self.desired_active:
            return
        if self.retry_job is not None:
            return
        if self.retry_attempts >= self.app.settings.max_reconnect_attempts:
            self._schedule_offline_retry()
            return

        self.retry_attempts += 1
        delay = compute_reconnect_delay_ms(self.retry_attempts, self.app.settings.reconnect_delay_ms)
        self.set_status(f"RECONNECT {self.retry_attempts}", WARN)
        self.app.record_reconnect(self.channel)
        log.warning("Camera %s reconnect scheduled in %sms (%s)", self.channel, delay, reason)
        self.retry_job = self.app.root.after(delay, self._do_reconnect)

    def _do_reconnect(self) -> None:
        self.retry_job = None
        if not self.desired_active:
            return
        log.info("Reconnecting camera %s", self.channel)
        self.restart_current_stream(force=True)

    def _read_video_counter(self) -> int | None:
        if self.active_player is None:
            return None
        media = self.active_player.get_media()
        if media is None:
            return None
        try:
            stats = vlc.MediaStats()
            if not media.get_stats(stats):
                return None
            return max(int(stats.displayed_pictures), int(stats.decoded_video))
        except Exception:
            return None

    def _read_playback_time_ms(self) -> int | None:
        if self.active_player is None:
            return None
        try:
            value = int(self.active_player.get_time())
        except Exception:
            return None
        if value < 0:
            return None
        return value

    def check_health(self) -> None:
        if not self.desired_active or self.active_player is None or self.retry_job is not None:
            return
        now = time.monotonic()
        elapsed = now - self.last_start_time
        if elapsed < 4:
            return
        try:
            state = self.active_player.get_state()
            playing = self.active_player.is_playing()
        except Exception:
            state = vlc.State.Error
            playing = False

        if state in (vlc.State.Error, vlc.State.Ended, vlc.State.Stopped):
            self.schedule_reconnect(f"state={state}")
            return

        counter = self._read_video_counter()
        if counter is not None:
            if counter > self.last_video_counter:
                self.last_video_counter = counter
                self.last_frame_progress_time = now
                self.set_status("LIVE", LIVE)
                self.retry_attempts = 0
                return

            stalled_for = now - self.last_frame_progress_time
            if state in (vlc.State.Opening, vlc.State.Buffering) or (playing or state == vlc.State.Playing):
                self.set_status("BUFFERING", BORDER_ACTIVE)
            else:
                # Paused can happen transiently; keep waiting while frames recently progressed.
                self.set_status("CONNECTING", TEXT_DIM)

            if stalled_for >= FRAME_STALL_SECONDS:
                self.schedule_reconnect(f"no frame progress for {stalled_for:.1f}s (state={state})")
            return

        if playing or state == vlc.State.Playing:
            self.last_frame_progress_time = now
            self.set_status("LIVE", LIVE)
            self.retry_attempts = 0
            return
        if state == vlc.State.Paused:
            self.set_status("CONNECTING", TEXT_DIM)
            if elapsed >= FRAME_STALL_SECONDS * 2:
                self.schedule_reconnect(f"state={state} without frame stats")
            return
        if state in (vlc.State.Opening, vlc.State.Buffering):
            self.set_status("BUFFERING", BORDER_ACTIVE)
            if elapsed >= FRAME_STALL_SECONDS * 2:
                self.schedule_reconnect(f"state={state} without frame stats")
            return

        stalled_for = now - self.last_frame_progress_time
        if stalled_for >= FRAME_STALL_SECONDS:
            self.schedule_reconnect(f"no playback progress for {stalled_for:.1f}s (state={state})")

    def stop(self) -> None:
        self.desired_active = False
        self.cancel_reconnect()
        self.cancel_offline_retry()
        for player in (self.grid_player, self.focus_player):
            if player is None:
                continue
            try:
                player.stop()
            except Exception:
                log.exception("Failed to stop camera %s", self.channel)
        self.active_player = None
        self.set_status("IDLE", TEXT_DIM)


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: "RTSPViewerApp"):
        super().__init__(app.root)
        self.app = app
        self.title("Viewer Settings")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        settings = app.settings
        self.vars = {
            "ip": tk.StringVar(value=settings.ip),
            "port": tk.StringVar(value=settings.port),
            "num_cams": tk.StringVar(value=str(settings.num_cams)),
            "rows": tk.StringVar(value=str(settings.rows)),
            "cols": tk.StringVar(value=str(settings.cols)),
            "ui_hide_ms": tk.StringVar(value=str(settings.ui_hide_ms)),
            "reconnect_delay_ms": tk.StringVar(value=str(settings.reconnect_delay_ms)),
            "max_reconnect_attempts": tk.StringVar(value=str(settings.max_reconnect_attempts)),
            "offline_retry_ms": tk.StringVar(value=str(settings.offline_retry_ms)),
            "start_fullscreen": tk.BooleanVar(value=settings.start_fullscreen),
        }

        self._build_form()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _row(self, parent: tk.Widget, row: int, label: str, widget: tk.Widget) -> None:
        tk.Label(parent, text=label, bg=BG, fg=TEXT, font=FONT_UI).grid(row=row, column=0, sticky="w", padx=8, pady=5)
        widget.grid(row=row, column=1, sticky="ew", padx=8, pady=5)

    def _build_form(self) -> None:
        outer = tk.Frame(self, bg=BG, padx=12, pady=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        title = tk.Label(outer, text="Connection and Layout", bg=BG, fg=TEXT, font=FONT_TITLE)
        title.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        self._row(outer, 1, "IP Address", tk.Entry(outer, textvariable=self.vars["ip"], width=32))
        self._row(outer, 2, "Port", tk.Entry(outer, textvariable=self.vars["port"], width=32))
        self._row(outer, 3, "Camera Count", tk.Entry(outer, textvariable=self.vars["num_cams"], width=32))
        self._row(outer, 4, "Rows", tk.Entry(outer, textvariable=self.vars["rows"], width=32))
        self._row(outer, 5, "Columns", tk.Entry(outer, textvariable=self.vars["cols"], width=32))
        self._row(outer, 6, "UI Hide (ms)", tk.Entry(outer, textvariable=self.vars["ui_hide_ms"], width=32))
        self._row(outer, 7, "Reconnect Delay (ms)", tk.Entry(outer, textvariable=self.vars["reconnect_delay_ms"], width=32))
        self._row(outer, 8, "Max Retries", tk.Entry(outer, textvariable=self.vars["max_reconnect_attempts"], width=32))
        self._row(outer, 9, "Offline Retry (ms)", tk.Entry(outer, textvariable=self.vars["offline_retry_ms"], width=32))

        fullscreen_row = tk.Checkbutton(
            outer,
            text="Start in fullscreen",
            variable=self.vars["start_fullscreen"],
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=BG,
        )
        fullscreen_row.grid(row=10, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 10))

        hint = tk.Label(
            outer,
            text="Credentials are read from UN/PW environment variables or .env only. Settings are saved to settings.json and applied on restart.",
            bg=BG,
            fg=TEXT_DIM,
            font=FONT_SMALL,
            wraplength=420,
            justify="left",
        )
        hint.grid(row=11, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 10))

        actions = tk.Frame(outer, bg=BG)
        actions.grid(row=12, column=0, columnspan=2, sticky="e", padx=8)

        save_button = tk.Label(actions, text="SAVE & EXIT", bg=PANEL, fg=BORDER_ACTIVE, padx=12, pady=6, cursor="hand2")
        save_button.pack(side="left", padx=(0, 8))
        save_button.bind("<Button-1>", lambda _event: self.save_and_exit())

        cancel_button = tk.Label(actions, text="CANCEL", bg=PANEL, fg=TEXT_DIM, padx=12, pady=6, cursor="hand2")
        cancel_button.pack(side="left")
        cancel_button.bind("<Button-1>", lambda _event: self.destroy())

    def save_and_exit(self) -> None:
        try:
            new_settings = AppSettings.from_form({key: var.get() for key, var in self.vars.items()})
            new_settings.save()
        except Exception as exc:
            messagebox.showerror("Invalid Settings", str(exc), parent=self)
            return

        self.destroy()
        self.app.restart_application()


class RTSPViewerApp:
    def __init__(self):
        self.settings = AppSettings.from_sources()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1400x860")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)

        self.fullscreen = self.settings.start_fullscreen
        self.focused_index: int | None = None
        self.switching = False
        self.page = 0
        self.ui_visible = True
        self.ui_hide_job = None
        self.clock_job = None
        self.monitor_job = None
        self.metrics_job = None
        self.last_motion_time = 0.0
        self.start_sequence_token = 0
        self.label_cache: dict[str, str] = {}
        self.closing = False
        self.total_reconnects = 0
        self.reconnects_by_camera: dict[int, int] = {}
        self.last_metrics_log_time = 0.0

        self.grid_vlc_instance = create_vlc_instance("grid")
        self.focus_vlc_instance = create_vlc_instance("focus")
        self.tiles: dict[int, CameraTile] = {}

        self.build_shell()
        self.build_grid()
        self.bind_keys()
        self.bind_activity()

        self.root.attributes("-fullscreen", self.fullscreen)
        self.show_page(0, start_streams=True)
        self.monitor_streams()
        self.tick_clock()
        self.report_metrics()

    @property
    def page_size(self) -> int:
        return self.settings.page_size

    @property
    def total_pages(self) -> int:
        return self.settings.total_pages

    def build_shell(self) -> None:
        self.topbar = tk.Frame(self.root, bg=PANEL, height=40)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        self.title_label = tk.Label(self.topbar, text="▣  RTSP", bg=PANEL, fg=TEXT, font=FONT_TITLE, padx=12)
        self.title_label.pack(side="left")

        self.status_label = tk.Label(self.topbar, text="", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=8)
        self.status_label.pack(side="left")

        self.page_label = tk.Label(self.topbar, text="", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=8)
        self.page_label.pack(side="left")

        self.settings_button = tk.Label(self.topbar, text="SETTINGS", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=10, cursor="hand2")
        self.settings_button.pack(side="right")
        self.settings_button.bind("<Button-1>", lambda _event: self.open_settings())

        self.audio_button = tk.Label(
            self.topbar,
            text="SOUND OFF",
            bg=PANEL,
            fg=TEXT_DIM,
            font=FONT_UI,
            padx=10,
            pady=2,
            bd=1,
            relief="solid",
            highlightthickness=0,
            cursor="hand2",
        )
        self.audio_button.bind("<Button-1>", lambda _event: self.toggle_focus_audio())

        self.retry_button = tk.Label(self.topbar, text="RETRY", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=10, cursor="hand2")
        self.retry_button.pack(side="right")
        self.retry_button.bind("<Button-1>", lambda _event: self.retry_visible_tiles(force=True))

        self.help_button = tk.Label(self.topbar, text="?", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=10, cursor="hand2")
        self.help_button.pack(side="right")
        self.help_button.bind("<Button-1>", lambda _event: self.show_help())

        self.back_button = tk.Label(self.topbar, text="◀  ALL", bg=PANEL, fg=BORDER_ACTIVE, font=("Segoe UI", 9, "bold"), padx=10, cursor="hand2")
        self.back_button.bind("<Button-1>", lambda _event: self.exit_focus())

        self.clock_label = tk.Label(self.topbar, text="", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=12)
        self.clock_label.pack(side="right")

        self.grid_frame = tk.Frame(self.root, bg=BG)
        self.grid_frame.pack(fill="both", expand=True, padx=0, pady=0)

    def build_grid(self) -> None:
        for r in range(self.settings.rows):
            self.grid_frame.grid_rowconfigure(r, weight=1)
        for c in range(self.settings.cols):
            self.grid_frame.grid_columnconfigure(c, weight=1)

    def configure_grid_weights(self, focused: bool) -> None:
        for r in range(self.settings.rows):
            self.grid_frame.grid_rowconfigure(r, weight=1 if (not focused or r == 0) else 0)
        for c in range(self.settings.cols):
            self.grid_frame.grid_columnconfigure(c, weight=1 if (not focused or c == 0) else 0)

    def get_or_create_tile(self, index: int) -> CameraTile:
        if index not in self.tiles:
            self.tiles[index] = CameraTile(self, index)
        return self.tiles[index]

    def bind_keys(self) -> None:
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<F11>", self.toggle_window_fullscreen)
        self.root.bind("<F1>", lambda _event: self.show_help())
        self.root.bind("<s>", lambda _event: self.open_settings())
        self.root.bind("<m>", lambda _event: self.toggle_focus_audio())
        self.root.bind("<M>", lambda _event: self.toggle_focus_audio())
        self.root.bind("<r>", lambda _event: self.retry_visible_tiles(force=True))
        self.root.bind("<Left>", lambda _event: self.prev_page())
        self.root.bind("<Right>", lambda _event: self.next_page())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def bind_activity(self) -> None:
        def on_motion(_event=None):
            current = time.monotonic()
            if current - self.last_motion_time > 0.1:
                self.last_motion_time = current
                self.show_ui()

        def on_key(_event=None):
            self.show_ui()

        self.root.bind("<Motion>", on_motion)
        self.root.bind("<Key>", on_key)

    def schedule_ui_hide(self) -> None:
        if self.ui_hide_job is not None:
            try:
                self.root.after_cancel(self.ui_hide_job)
            except Exception:
                pass
        self.ui_hide_job = self.root.after(self.settings.ui_hide_ms, self.hide_ui)

    def show_ui(self) -> None:
        if not self.ui_visible:
            self.ui_visible = True
            self.topbar.pack(side="top", fill="x")
            for tile in self.tiles.values():
                tile.set_chrome_visible(True)
            self.root.configure(cursor="")
        self.schedule_ui_hide()
        self.update_page_label()
        self.refresh_status_summary()
        self.update_focus_controls()

    def hide_ui(self) -> None:
        if self.focused_index is not None:
            return
        self.ui_visible = False
        self.topbar.pack_forget()
        for tile in self.tiles.values():
            tile.set_chrome_visible(False)
        self.root.configure(cursor="none")

    def update_focus_controls(self) -> None:
        if self.focused_index is None:
            self.audio_button.pack_forget()
            return
        tile = self.tiles.get(self.focused_index)
        enabled = bool(tile.audio_enabled) if tile is not None else False
        self.audio_button.config(text="SOUND ON" if enabled else "SOUND OFF", fg=TEXT if enabled else TEXT_DIM)
        self.audio_button.pack(side="right")

    def clear_start_queue(self) -> None:
        self.start_sequence_token += 1

    def queue_start_tiles(self, indexes: list[int]) -> None:
        self.clear_start_queue()
        token = self.start_sequence_token

        def start_next(position: int) -> None:
            if self.closing or token != self.start_sequence_token:
                return
            if position >= len(indexes):
                return
            index = indexes[position]
            tile = self.get_or_create_tile(index)
            tile.start_grid_stream(force=True)
            self.root.after(120, lambda: start_next(position + 1))

        start_next(0)

    def record_reconnect(self, channel: int) -> None:
        self.total_reconnects += 1
        self.reconnects_by_camera[channel] = self.reconnects_by_camera.get(channel, 0) + 1

    def report_metrics(self) -> None:
        if self.closing:
            return
        now = time.monotonic()
        if now - self.last_metrics_log_time >= 30:
            self.last_metrics_log_time = now
            active = [tile for tile in self.tiles.values() if tile.desired_active]
            offline = sum(1 for tile in active if tile.status_key.startswith("OFFLINE:"))
            reconnecting = sum(1 for tile in active if tile.status_key.startswith("RECONNECT"))
            log.info(
                "metrics active=%s reconnecting=%s offline=%s reconnect_total=%s",
                len(active),
                reconnecting,
                offline,
                self.total_reconnects,
            )
            if offline >= 3:
                log.warning("ALERT offline cameras=%s", offline)
        self.metrics_job = self.root.after(5000, self.report_metrics)

    def show_page(self, page: int, start_streams: bool = False) -> None:
        if page < 0 or page >= self.total_pages:
            return

        if self.focused_index is not None:
            self.exit_focus(restore_page=False)

        self.page = page
        start = page * self.page_size
        end = min(start + self.page_size, self.settings.num_cams)
        visible: list[int] = []

        for i in range(self.settings.num_cams):
            if start <= i < end:
                tile = self.get_or_create_tile(i)
                rel = i - start
                row = rel // self.settings.cols
                col = rel % self.settings.cols
                tile.grid_at(row, col)
                tile.set_active(False)
                tile.desired_active = True
                visible.append(i)
            elif i in self.tiles:
                tile = self.tiles[i]
                tile.desired_active = False
                tile.hide()
                tile.stop()

        self.configure_grid_weights(focused=False)
        self.back_button.pack_forget()
        self.update_page_label()
        self.refresh_status_summary()
        if start_streams:
            self.queue_start_tiles(visible)

    def next_page(self) -> None:
        if self.page < self.total_pages - 1:
            self.show_page(self.page + 1, start_streams=True)

    def prev_page(self) -> None:
        if self.page > 0:
            self.show_page(self.page - 1, start_streams=True)

    def update_page_label(self) -> None:
        text = f"Page {self.page + 1}/{self.total_pages}"
        if self.label_cache.get("page_label") == text:
            return
        self.label_cache["page_label"] = text
        self.page_label.config(text=text)

    def refresh_status_summary(self) -> None:
        live = sum(1 for tile in self.tiles.values() if tile.status_key.startswith("LIVE:"))
        reconnecting = sum(1 for tile in self.tiles.values() if tile.status_key.startswith("RECONNECT"))
        offline = sum(1 for tile in self.tiles.values() if tile.status_key.startswith("OFFLINE:"))
        if self.focused_index is not None:
            status = f"{self.settings.num_cams} CAMS  |  FOCUS CAM {self.focused_index + 1:02d}"
        else:
            status = f"{self.settings.num_cams} CAMS  |  {live} LIVE  {reconnecting} RETRY  {offline} OFFLINE"
        if self.label_cache.get("status_label") == status:
            return
        self.label_cache["status_label"] = status
        self.status_label.config(text=status)

    def toggle_focus(self, index: int) -> None:
        if self.focused_index == index:
            self.exit_focus()
        elif self.focused_index is None:
            self.enter_focus(index)

    def enter_focus(self, index: int) -> None:
        if self.switching:
            return
        self.switching = True
        self.clear_start_queue()
        self.focused_index = index

        focused_tile = self.get_or_create_tile(index)
        focused_tile.grid_at(0, 0)
        focused_tile.set_active(True)
        focused_tile.desired_active = True
        focused_tile.start_focus_stream(force=True)

        for i, tile in self.tiles.items():
            if i == index:
                continue
            tile.hide()
            tile.stop()
            tile.desired_active = False
            tile.set_active(False)

        self.configure_grid_weights(focused=True)
        self.back_button.pack(side="left")
        self.update_focus_controls()
        self.refresh_status_summary()
        self.switching = False
        self.show_ui()

    def exit_focus(self, restore_page: bool = True) -> None:
        if self.switching or self.focused_index is None:
            return

        self.switching = True
        focused = self.focused_index
        self.focused_index = None

        focused_tile = self.tiles.get(focused)
        if focused_tile is not None:
            focused_tile.start_grid_stream(force=True)

        self.configure_grid_weights(focused=False)
        self.back_button.pack_forget()
        self.audio_button.pack_forget()
        for tile in self.tiles.values():
            tile.set_active(False)

        self.switching = False
        if restore_page:
            self.show_page(self.page, start_streams=True)
        else:
            self.refresh_status_summary()

    def retry_visible_tiles(self, force: bool = False) -> None:
        if self.focused_index is not None:
            targets = [self.focused_index]
        else:
            start = self.page * self.page_size
            end = min(start + self.page_size, self.settings.num_cams)
            targets = list(range(start, end))

        for index in targets:
            if index in self.tiles:
                self.tiles[index].restart_current_stream(force=force)
        self.refresh_status_summary()

    def monitor_streams(self) -> None:
        if self.closing:
            return
        for tile in list(self.tiles.values()):
            if tile.desired_active:
                tile.check_health()
        self.resync_drifted_grid_tile()
        self.refresh_status_summary()
        self.monitor_job = self.root.after(2000, self.monitor_streams)

    def visible_grid_indexes(self) -> list[int]:
        if self.focused_index is not None:
            return []
        start = self.page * self.page_size
        end = min(start + self.page_size, self.settings.num_cams)
        return list(range(start, end))

    def resync_drifted_grid_tile(self) -> None:
        if self.focused_index is not None:
            return

        now = time.monotonic()
        candidates: list[tuple[CameraTile, int]] = []

        for index in self.visible_grid_indexes():
            tile = self.tiles.get(index)
            if tile is None:
                continue
            if not tile.desired_active or tile.active_mode != "grid":
                tile.drift_strikes = 0
                continue
            if tile.active_player is None or tile.retry_job is not None:
                tile.drift_strikes = 0
                continue
            if now - tile.last_start_time < 8:
                tile.drift_strikes = 0
                continue

            t_ms = tile._read_playback_time_ms()
            if t_ms is None:
                tile.drift_strikes = 0
                continue
            candidates.append((tile, t_ms))

        if len(candidates) < DRIFT_MIN_SAMPLES:
            for tile, _ in candidates:
                tile.drift_strikes = 0
            return

        times = sorted(value for _, value in candidates)
        median_time = times[len(times) // 2]

        worst_tile: CameraTile | None = None
        worst_lag = 0

        for tile, t_ms in candidates:
            lag_ms = median_time - t_ms
            if lag_ms >= DRIFT_THRESHOLD_MS:
                tile.drift_strikes += 1
                if lag_ms > worst_lag:
                    worst_lag = lag_ms
                    worst_tile = tile
            else:
                tile.drift_strikes = 0

        if worst_tile is None:
            return
        if worst_tile.drift_strikes < DRIFT_STRIKES_TO_RESYNC:
            return
        if now - worst_tile.last_drift_resync_time < DRIFT_RESYNC_COOLDOWN_SECONDS:
            return

        worst_tile.last_drift_resync_time = now
        worst_tile.drift_strikes = 0
        log.warning(
            "Camera %s resync due to drift: lag=%sms vs grid median",
            worst_tile.channel,
            worst_lag,
        )
        worst_tile.restart_current_stream(force=True)

    def tick_clock(self) -> None:
        if self.closing:
            return
        if self.ui_visible:
            text = time.strftime("%Y-%m-%d  %H:%M:%S")
            if self.label_cache.get("clock_label") != text:
                self.label_cache["clock_label"] = text
                self.clock_label.config(text=text)
        self.clock_job = self.root.after(1000, self.tick_clock)

    def toggle_focus_audio(self) -> None:
        if self.focused_index is None:
            return
        tile = self.tiles.get(self.focused_index)
        if tile is None:
            return
        tile.set_audio_enabled(not tile.audio_enabled)
        self.update_focus_controls()

    def show_help(self) -> None:
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Esc: exit focus or close\n"
            "F11: toggle fullscreen\n"
            "Left / Right: previous or next page\n"
            "M: toggle sound in focus view\n"
            "R: retry visible streams\n"
            "S: open settings\n"
            "F1 or ?: show this help",
            parent=self.root,
        )

    def open_settings(self) -> None:
        SettingsDialog(self)

    def restart_application(self) -> None:
        self.close()
        os.execl(sys.executable, sys.executable, str(Path(__file__).resolve()))

    def on_escape(self, _event=None) -> None:
        if self.focused_index is not None:
            self.exit_focus()
        else:
            self.close()

    def toggle_window_fullscreen(self, _event=None) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        for job in (self.ui_hide_job, self.clock_job, self.monitor_job, self.metrics_job):
            if job is None:
                continue
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        for tile in self.tiles.values():
            tile.stop()
            tile.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.show_ui()
        self.root.mainloop()


if __name__ == "__main__":
    try:
        RTSPViewerApp().run()
    except Exception:
        log.exception("Application failed to start")
        raise
