"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Main Tk application orchestrating UI and stream modules.
"""

from __future__ import annotations

import os
import sys
import time

import tkinter as tk
from tkinter import messagebox, simpledialog

from .core import (
    APP_TITLE,
    BG,
    BORDER_ACTIVE,
    DRIFT_MIN_SAMPLES,
    DRIFT_RESYNC_COOLDOWN_SECONDS,
    DRIFT_STRIKES_TO_RESYNC,
    DRIFT_THRESHOLD_MS,
    FONT_TITLE,
    FONT_UI,
    PANEL,
    TEXT,
    TEXT_DIM,
    build_restart_argv,
    launch_restart_process,
    log,
)
from .settings import AppSettings
from .stream import CameraTile, create_vlc_instance
from .ui import SettingsDialog


class RTSPViewerApp:
    def __init__(self):
        self.settings = AppSettings.from_sources()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1400x860")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)

        self.fullscreen = self.settings.start_fullscreen
        self.connection_ready = self.settings.has_valid_connection()
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
        self.update_quit_button_visibility()
        self.show_page(0, start_streams=self.connection_ready)
        if not self.connection_ready:
            self.root.after(150, self.prompt_for_required_connection_fields)
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

        self.title_label = tk.Label(self.topbar, text="CCTV Viewer", bg=PANEL, fg=TEXT, font=FONT_TITLE, padx=12)
        self.title_label.pack(side="left")

        self.status_label = tk.Label(self.topbar, text="", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=8)
        self.status_label.pack(side="left")

        self.page_label = tk.Label(self.topbar, text="", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=8)
        self.page_label.pack(side="left")

        self.quit_button = tk.Label(self.topbar, text="QUIT", bg=PANEL, fg=TEXT_DIM, font=FONT_UI, padx=10, cursor="hand2")
        self.quit_button.pack(side="right")
        self.quit_button.bind("<Button-1>", lambda _event: self.close())
        self.quit_button.pack_forget()

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

    def update_quit_button_visibility(self) -> None:
        if self.fullscreen:
            self.quit_button.pack(side="right", before=self.settings_button)
        else:
            self.quit_button.pack_forget()

    def prompt_for_required_connection_fields(self) -> None:
        needed = self.settings.connection_fields_requiring_input()
        if not needed:
            if not self.connection_ready:
                self.connection_ready = True
                self.queue_start_tiles(self.visible_grid_indexes())
            return

        display_names = {
            "UN": "Username (UN)",
            "PW": "Password (PW)",
            "IP": "IP/Host (IP)",
            "PORT": "Port (PORT)",
        }
        env_values = {
            "UN": os.getenv("UN", "").strip(),
            "PW": os.getenv("PW", ""),
            "IP": os.getenv("IP", "").strip(),
            "PORT": os.getenv("PORT", "").strip(),
        }

        entered: dict[str, str] = {}
        for key in needed:
            prompt = f"Enter {display_names[key]}"
            initial_value = env_values[key]
            if key == "PW":
                value = simpledialog.askstring("Missing Connection Setting", prompt, parent=self.root, show="*")
            else:
                value = simpledialog.askstring("Missing Connection Setting", prompt, parent=self.root, initialvalue=initial_value)
            if value is None:
                messagebox.showwarning(
                    "Connection Not Configured",
                    "Connection settings are incomplete. The app will stay open, but streams will not start.",
                    parent=self.root,
                )
                return
            entered[key] = value.strip() if key != "PW" else value

        merged = {
            "UN": entered.get("UN", env_values["UN"]),
            "PW": entered.get("PW", env_values["PW"]),
            "IP": entered.get("IP", env_values["IP"]),
            "PORT": entered.get("PORT", env_values["PORT"]),
        }

        try:
            AppSettings._save_env_values(
                username=merged["UN"],
                password=merged["PW"],
                ip=merged["IP"],
                port=merged["PORT"],
            )
            self.settings.username = merged["UN"]
            self.settings.password = merged["PW"]
            self.settings.ip = merged["IP"]
            self.settings.port = merged["PORT"]
            self.settings.validate_connection_settings()
        except Exception as exc:
            messagebox.showerror(
                "Invalid Connection Settings",
                f"{exc}\n\nPlease enter the missing or invalid values.",
                parent=self.root,
            )
            self.root.after(10, self.prompt_for_required_connection_fields)
            return

        if not self.connection_ready:
            self.connection_ready = True
            self.queue_start_tiles(self.visible_grid_indexes())

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
            focused_tile.set_audio_enabled(False)
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
            "Esc: exit focus\n"
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
        restart_args = build_restart_argv()
        try:
            launch_restart_process(restart_args)
        except Exception:
            log.exception("Failed to relaunch application")
            messagebox.showerror(
                "Restart Failed",
                "Could not restart the application. Please relaunch it manually.",
                parent=self.root,
            )
            return
        self.close()
        sys.exit(0)

    def on_escape(self, _event=None) -> None:
        if self.focused_index is not None:
            self.exit_focus()

    def toggle_window_fullscreen(self, _event=None) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        self.update_quit_button_visibility()

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


CCTVApp = RTSPViewerApp
