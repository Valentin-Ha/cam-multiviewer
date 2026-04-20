# Explanation: Architecture

This page describes the runtime architecture of RTSP Viewer.

## High-Level Structure

The app is implemented as a launcher plus package modules with three main runtime layers:

1. Configuration and utility layer (`viewer/core.py`, `viewer/settings.py`)
2. Per-camera tile state machine (`viewer/stream.py`)
3. Application orchestration and UI shell (`viewer/app.py`, `viewer/ui.py`)

`RTSP_viewer.py` is the runtime entrypoint and backward-compatible facade for tests and tooling.

## Core Types

- `AppSettings`
  - Loads from environment and `settings.json`
  - Validates and persists non-secret settings
  - Defined in `viewer/settings.py`
- `CameraTile`
  - Owns one camera channel UI and VLC players (grid and focus)
  - Handles health checks, reconnect scheduling, and status transitions
  - Defined in `viewer/stream.py`
- `RTSPViewerApp`
  - Builds window/UI, paging/focus behavior, timers, and aggregate status
  - Defined in `viewer/app.py`

## VLC Strategy

Two VLC instances are used:

- Grid instance: aggressive low-latency options for many simultaneous tiles
- Focus instance: higher caching profile for focused playback stability

Each tile lazily creates one player per mode and switches as needed.

## Event and Timer Model

Tkinter `after(...)` timers drive periodic tasks:

- stream health monitor (every 2s)
- clock update (every 1s)
- metrics report (every 5s)
- delayed reconnect/offline retry timers per tile

This avoids threads while keeping stream supervision responsive.

## Entry and Import Boundaries

- Start the application with `python RTSP_viewer.py`.
- Package modules under `viewer/` are designed for import by the launcher and tests.
- Running `viewer/app.py` or `viewer/__init__.py` directly is not a supported execution path.
