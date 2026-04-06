# RTSP Multi Stream Viewer Documentation

This documentation covers setup, operations, and internals of the RTSP Multi Stream Viewer application.

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

This project is currently implemented as a single Python entrypoint:

- `RTSP_viewer.py`

Tests are in:

- `tests/test_settings.py`
- `tests/test_reconnect_policy.py`
- `tests/test_reconnect_integration.py`
