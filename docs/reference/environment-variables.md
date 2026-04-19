# Reference: Environment Variables

Environment values are loaded from `.env` at startup.

## Required

- `UN`: RTSP username
- `PW`: RTSP password
- `IP`: camera/NVR IP or hostname
- `PORT`: RTSP port (1-65535)

If any required value is missing or invalid, the app prompts for the missing fields and writes the values to `.env`.

## Optional

- `LOG_LEVEL`
  - Default: `INFO`
  - Used to set Python logging level
- `RTSP_SCHEME`
  - Default: `rtsp`
  - Use `rtsps` to force secure RTSP URLs

## Security Notes

- Credentials are not written to `settings.json`.
- Logs attempt to mask `UN` and `PW` values.
- Avoid logging full RTSP URLs in custom changes.
