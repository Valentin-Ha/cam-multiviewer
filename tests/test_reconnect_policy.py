import unittest
from unittest.mock import patch

import second


class ReconnectPolicyTests(unittest.TestCase):
    def test_backoff_grows_and_caps_without_jitter(self):
        base = 2500
        with patch("second.random.randint", return_value=0):
            delays = [second.compute_reconnect_delay_ms(attempt, base) for attempt in range(1, 8)]
        self.assertEqual(delays[0], 2500)
        self.assertEqual(delays[1], 5000)
        self.assertEqual(delays[2], 10000)
        self.assertEqual(delays[3], 20000)
        self.assertEqual(delays[4], second.MAX_RECONNECT_DELAY_MS)
        self.assertEqual(delays[5], second.MAX_RECONNECT_DELAY_MS)

    def test_jitter_bounds(self):
        base = 2500
        for _ in range(50):
            delay = second.compute_reconnect_delay_ms(1, base)
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base + second.RECONNECT_JITTER_MAX_MS)


if __name__ == "__main__":
    unittest.main()
