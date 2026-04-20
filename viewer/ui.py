"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Tkinter dialogs used by the viewer app.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

from .core import (
    BG,
    BORDER_ACTIVE,
    FONT_SMALL,
    FONT_TITLE,
    FONT_UI,
    PANEL,
    TEXT,
    TEXT_DIM,
    log,
)
from .settings import AppSettings, validate_host


class ConnectionSettingsDialog(tk.Toplevel):
    """Dialog for editing connection credentials and settings stored in .env file."""

    def __init__(self, app: "RTSPViewerApp", parent: tk.Widget | None = None):
        super().__init__(app.root if parent is None else parent)
        self.app = app
        self.title("Connection Settings")
        self.configure(bg=BG)
        self.resizable(False, False)
        if parent:
            self.transient(parent)
        self.grab_set()

        self.vars = {
            "username": tk.StringVar(value=os.getenv("UN", "")),
            "password": tk.StringVar(value=os.getenv("PW", "")),
            "ip": tk.StringVar(value=os.getenv("IP", "")),
            "port": tk.StringVar(value=os.getenv("PORT", "")),
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

        title = tk.Label(outer, text="RTSP Connection & Credentials", bg=BG, fg=TEXT, font=FONT_TITLE)
        title.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 12))

        self._row(outer, 1, "Username (UN)", tk.Entry(outer, textvariable=self.vars["username"], width=32))
        self._row(outer, 2, "Password (PW)", tk.Entry(outer, textvariable=self.vars["password"], width=32, show="*"))
        self._row(outer, 3, "IP Address (IP)", tk.Entry(outer, textvariable=self.vars["ip"], width=32))
        self._row(outer, 4, "Port (PORT)", tk.Entry(outer, textvariable=self.vars["port"], width=32))

        hint = tk.Label(
            outer,
            text="These settings are saved to the .env file and take effect immediately after saving.",
            bg=BG,
            fg=TEXT_DIM,
            font=FONT_SMALL,
            wraplength=420,
            justify="left",
        )
        hint.grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 10))

        actions = tk.Frame(outer, bg=BG)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", padx=8)

        save_button = tk.Label(actions, text="Save & Restart", bg=PANEL, fg=BORDER_ACTIVE, padx=12, pady=6, cursor="hand2")
        save_button.pack(side="left", padx=(0, 8))
        save_button.bind("<Button-1>", lambda _event: self.save_and_exit())

        cancel_button = tk.Label(actions, text="CANCEL", bg=PANEL, fg=TEXT_DIM, padx=12, pady=6, cursor="hand2")
        cancel_button.pack(side="left")
        cancel_button.bind("<Button-1>", lambda _event: self.destroy())

    def save_and_exit(self) -> None:
        username = self.vars["username"].get().strip()
        password = self.vars["password"].get()
        ip = self.vars["ip"].get().strip()
        port = self.vars["port"].get().strip()

        if not all([username, password, ip, port]):
            messagebox.showerror("Invalid Input", "All fields (Username, Password, IP, Port) are required.", parent=self)
            return

        try:
            validate_host(ip)
        except Exception as exc:
            messagebox.showerror("Invalid IP/Host", str(exc), parent=self)
            return

        try:
            port_num = int(port)
        except (TypeError, ValueError):
            messagebox.showerror("Invalid Port", "Port must be a whole number.", parent=self)
            return

        if not (1 <= port_num <= 65535):
            messagebox.showerror("Invalid Port", "Port must be between 1 and 65535.", parent=self)
            return

        try:
            AppSettings._save_env_values(
                username=username,
                password=password,
                ip=ip,
                port=port,
            )
            log.info("Connection settings saved to .env")
            messagebox.showinfo(
                "Settings Saved",
                "Connection settings have been saved to .env.\nThe application will restart to apply these changes.",
                parent=self,
            )
            self.destroy()
            self.app.restart_application()
        except Exception as exc:
            messagebox.showerror("Save Failed", f"Could not save connection settings: {exc}", parent=self)


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
            "num_cams": tk.StringVar(value=str(settings.num_cams)),
            "rows": tk.StringVar(value=str(settings.rows)),
            "cols": tk.StringVar(value=str(settings.cols)),
            "ui_hide_ms": tk.StringVar(value=str(settings.ui_hide_ms)),
            "reconnect_delay_ms": tk.StringVar(value=str(settings.reconnect_delay_ms)),
            "max_reconnect_attempts": tk.StringVar(value=str(settings.max_reconnect_attempts)),
            "offline_retry_ms": tk.StringVar(value=str(settings.offline_retry_ms)),
            "rtsp_scheme": tk.StringVar(value=settings.rtsp_scheme),
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

        self._row(outer, 1, "Camera Count", tk.Entry(outer, textvariable=self.vars["num_cams"], width=32))
        self._row(outer, 2, "Rows", tk.Entry(outer, textvariable=self.vars["rows"], width=32))
        self._row(outer, 3, "Columns", tk.Entry(outer, textvariable=self.vars["cols"], width=32))
        self._row(outer, 4, "UI Hide (ms)", tk.Entry(outer, textvariable=self.vars["ui_hide_ms"], width=32))
        self._row(outer, 5, "Reconnect Delay (ms)", tk.Entry(outer, textvariable=self.vars["reconnect_delay_ms"], width=32))
        self._row(outer, 6, "Max Retries", tk.Entry(outer, textvariable=self.vars["max_reconnect_attempts"], width=32))
        self._row(outer, 7, "Offline Retry (ms)", tk.Entry(outer, textvariable=self.vars["offline_retry_ms"], width=32))
        protocol_row = tk.Frame(outer, bg=BG)
        tk.Radiobutton(
            protocol_row,
            text="RTSP",
            value="rtsp",
            variable=self.vars["rtsp_scheme"],
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=BG,
        ).pack(side="left")
        tk.Radiobutton(
            protocol_row,
            text="RTSPS",
            value="rtsps",
            variable=self.vars["rtsp_scheme"],
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=BG,
        ).pack(side="left", padx=(10, 0))
        self._row(outer, 8, "RTSP Protocol", protocol_row)

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
        fullscreen_row.grid(row=9, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 10))

        connection_button = tk.Label(outer, text="EDIT CONNECTION SETTINGS", bg=PANEL, fg=BORDER_ACTIVE, padx=12, pady=6, cursor="hand2")
        connection_button.grid(row=10, column=0, columnspan=2, sticky="e", padx=8, pady=(0, 10))
        connection_button.bind("<Button-1>", lambda _event: self.open_connection_settings())

        hint = tk.Label(
            outer,
            text="Layout settings and RTSP protocol are saved to settings.json and applied on restart. Connection settings (IP/Port/Credentials) are managed separately.",
            bg=BG,
            fg=TEXT_DIM,
            font=FONT_SMALL,
            wraplength=420,
            justify="left",
        )
        hint.grid(row=11, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 10))

        actions = tk.Frame(outer, bg=BG)
        actions.grid(row=12, column=0, columnspan=2, sticky="e", padx=8)

        save_button = tk.Label(actions, text="Save & Restart", bg=PANEL, fg=BORDER_ACTIVE, padx=12, pady=6, cursor="hand2")
        save_button.pack(side="left", padx=(0, 8))
        save_button.bind("<Button-1>", lambda _event: self.save_and_restart())

        cancel_button = tk.Label(actions, text="CANCEL", bg=PANEL, fg=TEXT_DIM, padx=12, pady=6, cursor="hand2")
        cancel_button.pack(side="left")
        cancel_button.bind("<Button-1>", lambda _event: self.destroy())

    def save_and_restart(self) -> None:
        if not self.persist_pending_settings(show_error=True):
            return

        self.destroy()
        self.app.restart_application()

    def persist_pending_settings(self, *, show_error: bool) -> bool:
        try:
            new_settings = AppSettings.from_form({key: var.get() for key, var in self.vars.items()})
            new_settings.save()
            self.app.settings = new_settings
            return True
        except Exception as exc:
            if show_error:
                messagebox.showerror("Invalid Settings", str(exc), parent=self)
            return False

    def open_connection_settings(self) -> None:
        self.persist_pending_settings(show_error=False)
        ConnectionSettingsDialog(self.app, parent=self)
