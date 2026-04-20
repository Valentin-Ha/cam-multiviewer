# RTSP Viewer

RTSP Viewer is a Python desktop RTSP multi-stream viewer built with Tkinter and VLC.

It is designed for low-latency grid viewing, single-camera focus mode, and automatic reconnect behavior when RTSP streams fail.

The runtime is modularized under the `viewer/` package, with `RTSP_viewer.py` retained as the launcher and compatibility facade.
## Features

- Multi-camera grid view with paging
- Focus mode for a single camera with optional audio
- Automatic reconnect with exponential backoff and jitter
- Offline retry mode after reconnect attempts are exhausted
- Drift detection and auto-resync for lagging grid tiles
- Runtime settings dialog with persisted non-secret configuration
- Separate connection settings editor for credentials, host, and port
- Rotating logs with credential masking

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install python-vlc python-dotenv
```

3. Ensure VLC media player is installed on the OS.
4. Copy `.env.example` to `.env` and fill in credentials.
5. Run the app:

```powershell
python RTSP_viewer.py
```

Note: `viewer/app.py` and other package modules are importable components, not standalone entry scripts.

## Project Layout

- `RTSP_viewer.py`: launcher and backward-compatible public surface for tests/tools
- `viewer/core.py`: paths, logging setup, constants, restart helpers
- `viewer/settings.py`: settings model, parsing, validation, persistence
- `viewer/stream.py`: VLC wiring, camera tile lifecycle, reconnect/backoff logic
- `viewer/ui.py`: settings and connection dialogs
- `viewer/app.py`: main Tk application orchestration
- `tests/`: reconnect and settings tests

## Configuration

Configuration is split by sensitivity:

- Secrets in `.env`:
  - `UN`
  - `PW`
- Connection endpoint in `.env`:
  - `IP`
  - `PORT`
- Runtime settings in `settings.json`:
  - `num_cams`, `rows`, `cols`, reconnect and UI timing values, `rtsp_scheme`, fullscreen preference

At startup, credentials are read from environment variables and `settings.json` is read for non-secret values.

If required connection fields are missing or invalid, the app prompts for values and saves them to `.env`.

## Keyboard Shortcuts

- `Esc`: exit focus mode
- `F11`: toggle fullscreen
- `Left` / `Right`: previous or next page
- `M`: toggle sound for focused tile
- `R`: retry visible streams
- `S`: open settings dialog
- `F1` or `?`: show keyboard help

## Logging

- Logs are written to `logs/app.log` with rotation (5 MB x 5 backups)
- `LOG_LEVEL` can be set via environment (`INFO` by default)
- Credential values are masked in log output

## Tests

Run the test suite:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Current tests validate settings handling and reconnect delay behavior.

## Documentation

Project documentation is organized under `docs/` using a Diataxis-style split:

- Tutorials: learning-oriented walkthroughs
- How-to guides: task-oriented operational steps
- Reference: exact configuration and control details
- Explanation: architecture and design rationale

Start at `docs/index.md`.

## Local Docs Site (Optional)

If you want a browsable docs site:

```powershell
pip install mkdocs
mkdocs serve
```

This uses `mkdocs.yml` included in the repository.
