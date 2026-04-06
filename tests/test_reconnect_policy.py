"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>."""

import unittest
from unittest.mock import patch

import CCTV_viewer


class ReconnectPolicyTests(unittest.TestCase):
    def test_backoff_grows_and_caps_without_jitter(self):
        base = 2500
        with patch("CCTV_viewer.random.randint", return_value=0):
            delays = [CCTV_viewer.compute_reconnect_delay_ms(attempt, base) for attempt in range(1, 8)]
        self.assertEqual(delays[0], 2500)
        self.assertEqual(delays[1], 5000)
        self.assertEqual(delays[2], 10000)
        self.assertEqual(delays[3], 20000)
        self.assertEqual(delays[4], CCTV_viewer.MAX_RECONNECT_DELAY_MS)
        self.assertEqual(delays[5], CCTV_viewer.MAX_RECONNECT_DELAY_MS)

    def test_jitter_bounds(self):
        base = 2500
        for _ in range(50):
            delay = CCTV_viewer.compute_reconnect_delay_ms(1, base)
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base + CCTV_viewer.RECONNECT_JITTER_MAX_MS)


if __name__ == "__main__":
    unittest.main()
