"""Tests for the cursor-halo overlay shared state (Qt-free)."""
from __future__ import annotations

import unittest

from app.ui.overlay_state import OverlayPositionStore


class TestOverlayPositionStore(unittest.TestCase):
    def setUp(self):
        self.store = OverlayPositionStore()

    def test_update_and_read(self):
        self.store.update((100.0, 200.0))
        x, y, ts, active, gesture, gts, cts = self.store.read()
        self.assertEqual((x, y), (100.0, 200.0))
        self.assertTrue(active)
        self.assertGreater(ts, 0.0)
        self.assertIsNone(gesture)
        self.assertEqual(cts, 0.0)

    def test_update_overwrites(self):
        self.store.update((1.0, 2.0))
        self.store.update((300.0, 400.0))
        x, y, *_ = self.store.read()
        self.assertEqual((x, y), (300.0, 400.0))

    def test_set_gesture(self):
        self.store.set_gesture("PINCH")
        _, _, _, _, gesture, gts, _ = self.store.read()
        self.assertEqual(gesture, "PINCH")
        self.assertGreater(gts, 0.0)

    def test_set_clear_deactivates(self):
        self.store.update((1.0, 2.0))
        self.store.set_clear()
        _, _, _, active, *_ = self.store.read()
        self.assertFalse(active)

    def test_notify_click_records_timestamp(self):
        self.store.notify_click()
        *_, click_ts = self.store.read()
        self.assertGreater(click_ts, 0.0)

    def test_concurrent_writes_are_safe(self):
        import threading

        errors: list[Exception] = []

        def writer(offset: float) -> None:
            try:
                for i in range(200):
                    self.store.update((float(i + offset), 50.0))
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(float(n),)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        x, y, *_ = self.store.read()
        self.assertIsInstance(x, float)
        self.assertIsInstance(y, float)


if __name__ == "__main__":
    unittest.main()