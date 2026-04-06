# Reference: Settings Schema

`settings.json` stores non-secret runtime settings.

## Keys

- `num_cams` (int)
  - Minimum: 1
  - Default: 16
- `rows` (int)
  - Minimum: 1
  - Default: 3
- `cols` (int)
  - Minimum: 1
  - Default: 3
- `ui_hide_ms` (int)
  - Minimum: 250
  - Default: 2000
- `reconnect_delay_ms` (int)
  - Minimum: 250
  - Default: 2500
- `max_reconnect_attempts` (int)
  - Minimum: 1
  - Default: 4
- `offline_retry_ms` (int)
  - Minimum: 1000
  - Default: 60000
- `start_fullscreen` (bool)
  - Default: true

## Derived Values

- Page size = `rows * cols`
- Total pages = `ceil(num_cams / page_size)`

## Persistence Rules

- Settings are saved atomically to reduce file corruption risk.
- Secrets (`username`, `password`) are excluded from persisted payload.
