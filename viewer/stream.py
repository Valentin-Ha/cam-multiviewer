"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>.

Streaming and camera tile logic.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import tkinter as tk
import vlc

from .core import (
    BORDER,
    BORDER_ACTIVE,
    CARD,
    CARD_HOVER,
    ERROR,
    FOCUS_SUBTYPE,
    FONT_CAM,
    FONT_SMALL,
    FRAME_STALL_SECONDS,
    GRID_SUBTYPE,
    LIVE,
    MAX_RECONNECT_DELAY_MS,
    PAD,
    RECONNECT_JITTER_MAX_MS,
    TEXT,
    TEXT_DIM,
    WARN,
    log,
)

if TYPE_CHECKING:
    from .app import RTSPViewerApp
    from .settings import AppSettings


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
    scheme = "rtsps" if settings.rtsp_scheme == "rtsps" else "rtsp"
    return (
        f"{scheme}://{settings.username}:{settings.password}@{settings.ip}:{settings.port}"
        f"/cam/realmonitor?channel={channel}&subtype={subtype}"
    )


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
