# Explanation: Reconnect and Health Model

## Why a Hybrid Health Signal

VLC state flags alone can be misleading in live RTSP scenarios. The app therefore combines:

- VLC state (`Playing`, `Buffering`, `Paused`, `Error`, etc.)
- playback progression indicators:
  - displayed frame counter
  - decoded video counter
  - playback time for drift detection

This reduces false reconnects while still reacting to real stalls.

## Reconnect Policy

For each failure event:

1. Increment reconnect attempt counter.
2. Compute delay using exponential backoff with random jitter.
3. Schedule retry until `max_reconnect_attempts` is reached.
4. Enter `OFFLINE` state and schedule long retry (`offline_retry_ms`).

Delay function summary:

- Core delay grows as $base * 2^{attempt-1}$
- Core delay is capped at a max value
- Random jitter is added in range $[0, jitter_max]$

## Stall Detection

A tile is considered stalled when frame counters stop advancing for at least `FRAME_STALL_SECONDS` while active.

When stalled, the tile schedules reconnect unless currently reconnecting.

## Drift Resync Across Grid

In grid mode, the app compares visible tile playback time to the median. If a tile lags beyond threshold repeatedly, it is restarted to resync with peers.

Safeguards include:

- minimum sample count
- strike accumulation requirement
- cooldown between resync actions
