"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Settings model and validation helpers.
"""

from __future__ import annotations

import json
import math
import os
import socket
import sys
import tempfile
from dataclasses import asdict, dataclass
from ipaddress import ip_address
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog

from dotenv import set_key

from .core import (
    DEFAULT_COLS,
    DEFAULT_MAX_RECONNECT_ATTEMPTS,
    DEFAULT_NUM_CAMS,
    DEFAULT_OFFLINE_RETRY_MS,
    DEFAULT_RECONNECT_DELAY_MS,
    DEFAULT_ROWS,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_SCHEME,
    DEFAULT_UI_HIDE_MS,
    ENV_PATH,
    SETTINGS_PATH,
    log,
)


def _compat_module():
    return sys.modules.get("RTSP_viewer")


def get_settings_path() -> Path:
    compat = _compat_module()
    if compat is not None:
        candidate = getattr(compat, "SETTINGS_PATH", None)
        if isinstance(candidate, Path):
            return candidate
    return SETTINGS_PATH


def get_env_path() -> Path:
    compat = _compat_module()
    if compat is not None:
        candidate = getattr(compat, "ENV_PATH", None)
        if isinstance(candidate, Path):
            return candidate
    return ENV_PATH


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
    rtsp_scheme: str = DEFAULT_RTSP_SCHEME
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
            "port": DEFAULT_RTSP_PORT,
            "num_cams": DEFAULT_NUM_CAMS,
            "rows": DEFAULT_ROWS,
            "cols": DEFAULT_COLS,
            "ui_hide_ms": DEFAULT_UI_HIDE_MS,
            "reconnect_delay_ms": DEFAULT_RECONNECT_DELAY_MS,
            "max_reconnect_attempts": DEFAULT_MAX_RECONNECT_ATTEMPTS,
            "offline_retry_ms": DEFAULT_OFFLINE_RETRY_MS,
            "rtsp_scheme": DEFAULT_RTSP_SCHEME,
            "start_fullscreen": True,
        }

        settings_path = get_settings_path()
        if settings_path.exists():
            try:
                stored = json.loads(settings_path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    for key in (
                        "num_cams",
                        "rows",
                        "cols",
                        "ui_hide_ms",
                        "reconnect_delay_ms",
                        "max_reconnect_attempts",
                        "offline_retry_ms",
                        "rtsp_scheme",
                        "start_fullscreen",
                    ):
                        if key in stored:
                            data[key] = stored[key]
            except Exception:
                log.exception("Failed to load settings.json; using env/defaults")

        data["username"] = os.getenv("UN", "").strip()
        data["password"] = os.getenv("PW", "")
        data["ip"] = os.getenv("IP", str(data.get("ip", "")).strip())
        env_port = os.getenv("PORT")
        if env_port is not None and env_port.strip():
            data["port"] = env_port.strip()
        else:
            data["port"] = str(data.get("port", DEFAULT_RTSP_PORT)).strip()
        env_scheme = os.getenv("RTSP_SCHEME")
        if env_scheme is not None and env_scheme.strip():
            data["rtsp_scheme"] = env_scheme.strip()

        repaired = False
        data["num_cams"], changed = cls._coerce_int_setting(
            "num_cams",
            data.get("num_cams"),
            DEFAULT_NUM_CAMS,
            min_value=1,
        )
        repaired = repaired or changed
        data["rows"], changed = cls._coerce_int_setting(
            "rows",
            data.get("rows"),
            DEFAULT_ROWS,
            min_value=1,
        )
        repaired = repaired or changed
        data["cols"], changed = cls._coerce_int_setting(
            "cols",
            data.get("cols"),
            DEFAULT_COLS,
            min_value=1,
        )
        repaired = repaired or changed
        data["ui_hide_ms"], changed = cls._coerce_int_setting(
            "ui_hide_ms",
            data.get("ui_hide_ms"),
            DEFAULT_UI_HIDE_MS,
            min_value=250,
        )
        repaired = repaired or changed
        data["reconnect_delay_ms"], changed = cls._coerce_int_setting(
            "reconnect_delay_ms",
            data.get("reconnect_delay_ms"),
            DEFAULT_RECONNECT_DELAY_MS,
            min_value=250,
        )
        repaired = repaired or changed
        data["max_reconnect_attempts"], changed = cls._coerce_int_setting(
            "max_reconnect_attempts",
            data.get("max_reconnect_attempts"),
            DEFAULT_MAX_RECONNECT_ATTEMPTS,
            min_value=1,
        )
        repaired = repaired or changed
        data["offline_retry_ms"], changed = cls._coerce_int_setting(
            "offline_retry_ms",
            data.get("offline_retry_ms"),
            DEFAULT_OFFLINE_RETRY_MS,
            min_value=1000,
        )
        repaired = repaired or changed
        data["rtsp_scheme"], changed = cls._coerce_rtsp_scheme(
            data.get("rtsp_scheme"),
            default=DEFAULT_RTSP_SCHEME,
        )
        repaired = repaired or changed
        data["start_fullscreen"] = parse_bool(data.get("start_fullscreen", True), default=True)

        settings = cls(**data)
        settings.validate_ui_settings()
        if repaired or not settings_path.exists():
            settings.save()
        return settings

    @staticmethod
    def _coerce_int_setting(
        name: str,
        raw_value: object,
        default: int,
        *,
        min_value: int | None = None,
    ) -> tuple[int, bool]:
        try:
            value = int(raw_value)
        except (TypeError, ValueError, OverflowError):
            log.warning("Invalid settings value for %s=%r; using default %s", name, raw_value, default)
            return default, True
        if min_value is not None and value < min_value:
            log.warning("Invalid settings value for %s=%r; using default %s", name, raw_value, default)
            return default, True
        return value, False

    @staticmethod
    def _coerce_rtsp_scheme(raw_value: object, default: str) -> tuple[str, bool]:
        candidate = str(raw_value).strip().lower() if raw_value is not None else ""
        if candidate in {"rtsp", "rtsps"}:
            return candidate, False
        log.warning("Invalid settings value for rtsp_scheme=%r; using default %s", raw_value, default)
        return default, True

    @staticmethod
    def _save_env_values(username: str, password: str, ip: str, port: str) -> None:
        updates = {
            "UN": username,
            "PW": password,
            "IP": ip,
            "PORT": port,
        }
        env_path = get_env_path()
        for key, value in updates.items():
            set_key(str(env_path), key, value, quote_mode="auto")

        os.environ["UN"] = username
        os.environ["PW"] = password
        os.environ["IP"] = ip
        os.environ["PORT"] = port

    @classmethod
    def bootstrap_missing_config(cls, default_ip: str, default_port: str) -> dict[str, str] | None:
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            return None

        try:
            messagebox.showwarning(
                "Missing Configuration",
                "Credentials or connection settings are missing.\n"
                "Enter values to continue. They will be saved to .env.",
                parent=root,
            )

            username = simpledialog.askstring("Required", "Username (UN)", parent=root)
            if username is None:
                return None
            password = simpledialog.askstring("Required", "Password (PW)", parent=root, show="*")
            if password is None:
                return None
            ip = simpledialog.askstring("Required", "IP/Host (IP)", parent=root, initialvalue=default_ip)
            if ip is None:
                return None
            port = simpledialog.askstring("Required", "Port (PORT)", parent=root, initialvalue=default_port)
            if port is None:
                return None

            values = {
                "username": username.strip(),
                "password": password,
                "ip": ip.strip(),
                "port": port.strip(),
            }

            if not all(values.values()):
                messagebox.showerror("Invalid Input", "All fields are required.", parent=root)
                return None

            cls._save_env_values(
                username=values["username"],
                password=values["password"],
                ip=values["ip"],
                port=values["port"],
            )
            return values
        finally:
            root.destroy()

    @classmethod
    def from_form(cls, data: dict[str, object]) -> "AppSettings":
        username = os.getenv("UN", "").strip()
        password = os.getenv("PW", "")
        ip = os.getenv("IP", "").strip()
        port = os.getenv("PORT", "").strip()
        settings = cls(
            username=username,
            password=password,
            ip=ip,
            port=port if port else DEFAULT_RTSP_PORT,
            num_cams=int(data["num_cams"]),
            rows=int(data["rows"]),
            cols=int(data["cols"]),
            ui_hide_ms=int(data["ui_hide_ms"]),
            reconnect_delay_ms=int(data["reconnect_delay_ms"]),
            max_reconnect_attempts=int(data["max_reconnect_attempts"]),
            offline_retry_ms=int(data.get("offline_retry_ms", DEFAULT_OFFLINE_RETRY_MS)),
            rtsp_scheme=cls._coerce_rtsp_scheme(data.get("rtsp_scheme", DEFAULT_RTSP_SCHEME), default=DEFAULT_RTSP_SCHEME)[0],
            start_fullscreen=parse_bool(data["start_fullscreen"], default=True),
        )
        settings.validate_ui_settings()
        return settings

    def validate_ui_settings(self) -> None:
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

    def validate_connection_settings(self) -> None:
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

    def validate(self) -> None:
        self.validate_ui_settings()
        self.validate_connection_settings()

    def connection_fields_requiring_input(self) -> list[str]:
        fields: list[str] = []
        if not self.username.strip():
            fields.append("UN")
        if not self.password:
            fields.append("PW")

        host = self.ip.strip()
        if not host:
            fields.append("IP")
        else:
            try:
                validate_host(host)
            except RuntimeError:
                fields.append("IP")

        raw_port = str(self.port).strip()
        if not raw_port:
            fields.append("PORT")
        else:
            try:
                port_num = int(raw_port)
            except (TypeError, ValueError):
                fields.append("PORT")
            else:
                if not (1 <= port_num <= 65535):
                    fields.append("PORT")
        return fields

    def has_valid_connection(self) -> bool:
        try:
            self.validate_connection_settings()
            return True
        except RuntimeError:
            return False

    def save(self) -> None:
        payload = asdict(self)
        payload.pop("username", None)
        payload.pop("password", None)
        payload.pop("ip", None)
        payload.pop("port", None)
        atomic_write_json(get_settings_path(), payload)
