# Tutorial: First Run

This tutorial walks through launching RTSP Viewer for the first time.

## Prerequisites

- Python 3.10+ installed
- VLC media player installed on the machine
- Camera/NVR RTSP credentials and host details

## Step 1: Install Python Dependencies

From the project folder:

```powershell
pip install python-vlc python-dotenv
```

## Step 2: Configure Secrets

Copy `.env.example` to `.env` and set values:

```dotenv
UN=your_username
PW=your_password
IP=192.168.1.50
PORT=554
```

Optional:

- `LOG_LEVEL=DEBUG` for verbose logs
- `RTSP_SCHEME=rtsps` if your endpoint requires secure RTSP

## Step 3: Review Runtime Settings

`settings.json` stores non-secret app settings (layout and retry behavior).

Defaults include:

- `num_cams`: 16
- `rows`: 3
- `cols`: 3
- `ui_hide_ms`: 2000
- `reconnect_delay_ms`: 2500
- `max_reconnect_attempts`: 4
- `offline_retry_ms`: 60000
- `rtsp_scheme`: `rtsp`
- `start_fullscreen`: true

## Step 4: Launch the App

```powershell
python RTSP_viewer.py
```

At startup, the app:

1. Loads `.env` values
2. Loads `settings.json`
3. Creates the initial page of tiles
4. Starts streams in sequence to reduce startup spikes

If required connection values (`UN`, `PW`, `IP`, `PORT`) are missing or invalid, the app prompts for the missing fields and writes them to `.env`.

## Step 5: Verify Healthy Operation

Look for:

- Tile statuses changing to `LIVE`
- A populated top bar with page and camera summary
- Log file updates in `logs/app.log`

If streams do not connect, go to How-to: Maintenance and Debugging.
