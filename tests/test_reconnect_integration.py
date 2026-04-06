"""Copyright (c) 2026 Valentin Haase <feststoff_holz6t@icloud.com>."""

import random
import unittest

import CCTV_viewer


class ReconnectIntegrationTests(unittest.TestCase):
    def test_multi_camera_initial_reconnect_spread(self):
        random.seed(7)
        delays = [CCTV_viewer.compute_reconnect_delay_ms(1, 2500) for _ in range(16)]
        self.assertTrue(all(2500 <= value <= 3500 for value in delays))
        self.assertGreater(len(set(delays)), 8)


if __name__ == "__main__":
    unittest.main()
