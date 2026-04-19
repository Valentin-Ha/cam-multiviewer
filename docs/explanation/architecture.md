# Explanation: Architecture

This page describes the runtime architecture of RTSP Viewer.

## High-Level Structure

The app is implemented in a single module with three main runtime layers:

1. Configuration and utility layer
2. Per-camera tile state machine (`CameraTile`)
3. Application orchestration and UI shell (`RTSPViewerApp`)

## Core Types

- `AppSettings`
  - Loads from environment and `settings.json`
  - Validates and persists non-secret settings
- `CameraTile`
  - Owns one camera channel UI and VLC players (grid and focus)
  - Handles health checks, reconnect scheduling, and status transitions
- `RTSPViewerApp`
  - Builds window/UI, paging/focus behavior, timers, and aggregate status

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
