# RTSP Viewer Documentation

This documentation covers setup, operations, and internals of the RTSP Viewer application (an RTSP multi-stream viewer).

The structure follows Diataxis:

- Tutorial: learn by doing
- How-to: solve concrete tasks
- Reference: exact technical details
- Explanation: design and tradeoffs

## Recommended Reading Order

1. Tutorial: First Run
2. How-to: Common Operations
3. Reference pages for exact values and shortcuts
4. Explanation pages when changing code or troubleshooting complex behavior

## Scope

This project is organized as a launcher plus modular runtime package:

- `RTSP_viewer.py` (launcher and compatibility facade)
- `viewer/core.py` (constants, logging, runtime path helpers)
- `viewer/settings.py` (settings/env parsing, validation, persistence)
- `viewer/stream.py` (VLC stream and reconnect logic)
- `viewer/ui.py` (Tk dialogs)
- `viewer/app.py` (application orchestration)

Run the app via `RTSP_viewer.py`.

Tests are in:

- `tests/test_settings.py`
- `tests/test_reconnect_policy.py`
- `tests/test_reconnect_integration.py`
