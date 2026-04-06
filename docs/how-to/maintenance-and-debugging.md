# How-to: Maintenance and Debugging

## Run Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

This validates reconnect delay behavior and settings loading/saving invariants.

## Increase Log Detail

Set in `.env`:

```dotenv
LOG_LEVEL=DEBUG
```

Restart the app and inspect `logs/app.log`.

## Diagnose Missing Streams

Checklist:

1. Verify `.env` has valid `UN`, `PW`, `IP`, `PORT`.
2. Confirm the camera host is reachable from this machine.
3. Confirm VLC is installed and available to `python-vlc`.
4. Check whether tile statuses cycle through `RECONNECT` and then `OFFLINE`.
5. Review `logs/app.log` for connection or state errors.

## Tune Reconnect Behavior

Tune these keys in `settings.json`:

- `reconnect_delay_ms`
- `max_reconnect_attempts`
- `offline_retry_ms`

Reconnect delay uses exponential growth with random jitter and a max cap.

## Recover from Invalid Settings

If startup fails after a bad change:

1. Close app.
2. Fix `settings.json` values to valid ranges.
3. Relaunch.

Validation rules are listed in the Settings Schema reference.
