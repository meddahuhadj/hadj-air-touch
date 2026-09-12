"""Command-line interface for headless / test mode."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from app.logging_conf import setup_logging


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hadj_air_touch",
        description="HADJ AIR TOUCH – virtual touch via webcam.",
    )
    p.add_argument("--headless", action="store_true", help="Run without GUI.")
    p.add_argument("--self-test", action="store_true", help="Run built-in self-test suite.")
    p.add_argument("--doctor", action="store_true",
                   help="Print a system diagnostics report and exit.")
    p.add_argument("--camera-index", type=int, default=0)
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--config", default=None, help="Path to settings JSON.")
    return p


def run_cli(args: argparse.Namespace) -> int:
    setup_logging(getattr(logging, args.log_level.upper(), logging.INFO))
    log = logging.getLogger(__name__)

    if args.self_test:
        return _run_self_test()

    if args.doctor:
        from app.diagnostics import run_doctor  # noqa: PLC0415
        return run_doctor()

    if args.headless:
        return _run_headless(args)

    from app.ui.main_window import MainWindow  # noqa: PLC0415
    from app.ui.theme import apply_theme  # noqa: PLC0415
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    qapp = QApplication(sys.argv)
    apply_theme(dark=True)
    win = MainWindow(args)
    win.show()
    return qapp.exec()


def _run_headless(args: argparse.Namespace) -> int:
    """Run the full interaction pipeline without any GUI window."""
    from app.camera.capture import CameraCapture  # noqa: PLC0415
    from app.config import Settings  # noqa: PLC0415
    from app.core.controller import PipelineController  # noqa: PLC0415
    from app.core.events import EventBus  # noqa: PLC0415
    from app.gestures.engine import GestureEngine  # noqa: PLC0415
    from app.privacy.guard import PrivacyGuard  # noqa: PLC0415
    from app.tracking.hand_tracker import HandTracker  # noqa: PLC0415
    from app.tracking.quality import TrackingQualityMonitor  # noqa: PLC0415
    from app.virtual_touch.engine import VirtualTouchEngine  # noqa: PLC0415
    from app.windows_input.dispatcher import InputDispatcher  # noqa: PLC0415
    from app.windows_input.keyboard import KeyboardController  # noqa: PLC0415
    from app.windows_input.mouse import MouseController  # noqa: PLC0415
    from app.windows_input.screen import ScreenManager  # noqa: PLC0415
    from app.calibration.calibrator import Calibrator  # noqa: PLC0415
    from app.voice.controller import VoiceController  # noqa: PLC0415

    log = logging.getLogger(__name__)
    settings = Settings(args.config) if args.config else Settings()
    camera_cfg = settings.config.camera
    if args.camera_index is not None:
        camera_cfg.index = args.camera_index

    bus = EventBus()
    camera = CameraCapture(
        camera_index=camera_cfg.index,
        width=camera_cfg.width,
        height=camera_cfg.height,
        fps=camera_cfg.fps,
        mirror=camera_cfg.mirror,
    )
    tracker = HandTracker()
    gesture_engine = GestureEngine()
    for name, enabled in settings.config.gestures.items():
        gesture_engine.configured_gestures[name] = enabled
    vt_engine = VirtualTouchEngine()
    vt_engine.apply_settings(
        touch_depth_cm=settings.config.virtual_touch.touch_depth_cm,
        sensitivity=settings.config.virtual_touch.sensitivity,
    )
    mouse = MouseController()
    kb = KeyboardController()
    screen_mgr = ScreenManager()
    primary = screen_mgr.primary
    calibrator = Calibrator(
        screen_width=(primary.width if primary else 1920),
        screen_height=(primary.height if primary else 1080),
    )
    quality_mon = TrackingQualityMonitor()

    pipeline = PipelineController(bus, settings)
    pipeline.set_camera(camera)
    pipeline.set_tracker(tracker)
    pipeline.set_gesture_engine(gesture_engine)
    pipeline.set_virtual_touch_engine(vt_engine)
    pipeline.set_screen_manager(screen_mgr)
    pipeline.set_calibrator(calibrator)
    pipeline.set_quality_monitor(quality_mon)

    dispatcher = InputDispatcher(bus, mouse, kb, calibrator, settings)
    pipeline.set_dispatcher(dispatcher)

    guard = PrivacyGuard(bus)
    voice = VoiceController(bus, language=settings.config.language)

    if not camera.open():
        log.error("Could not open camera %s", camera_cfg.index)
        return 1

    pipeline.start()
    log.info("Headless mode running – camera %s, mode %s. Ctrl+C to exit.",
             camera_cfg.index, settings.config.mode)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        log.info("Shutting down headless mode...")
    finally:
        pipeline.stop()
        camera.stop()
        voice.stop()
    return 0


def _run_self_test() -> int:
    """Run a lightweight self-test that works without any third-party deps."""
    from app.calibration.homography import solve_homography, apply_homography  # noqa: PLC0415
    from app.gestures.engine import GestureEngine  # noqa: PLC0415
    from app.virtual_touch.engine import VirtualTouchEngine, TouchState  # noqa: PLC0415
    from app.virtual_touch.smoothing import ExponentialSmoothingFilter  # noqa: PLC0415

    ok = True

    # 1) Homography round-trip
    try:
        pts_src = [(0, 0), (640, 0), (640, 480), (0, 480)]
        pts_dst = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        H = solve_homography(pts_src, pts_dst)
        test_pt = (320, 240)
        mapped = apply_homography(H, test_pt)
        assert abs(mapped[0] - 960) < 5 and abs(mapped[1] - 540) < 5, mapped
        print(f"  [PASS] Homography: {test_pt} -> {mapped}")
    except Exception as exc:
        print(f"  [FAIL] Homography: {exc}")
        ok = False

    # 2) Gesture engine
    try:
        engine = GestureEngine()
        print(f"  [PASS] GestureEngine created – {len(engine.configured_gestures)} gestures")
    except Exception as exc:
        print(f"  [FAIL] GestureEngine: {exc}")
        ok = False

    # 3) Virtual touch state machine
    try:
        vte = VirtualTouchEngine()
        assert vte.state == TouchState.IDLE
        vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        assert vte.state in (TouchState.POINTING, TouchState.APPROACHING), vte.state
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        assert vte.state == TouchState.APPROACHING, vte.state
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=300)
        assert vte.state == TouchState.VIRTUAL_TOUCH, vte.state
        vte.update(touching=False, finger_on_screen=False, elapsed_ms=50)
        assert vte.state == TouchState.RELEASING, vte.state
        print(f"  [PASS] VirtualTouchEngine state transitions OK (final={vte.state})")
    except Exception as exc:
        print(f"  [FAIL] VirtualTouchEngine: {exc}")
        ok = False

    # 4) Smoothing
    try:
        filt = ExponentialSmoothingFilter(alpha=0.5)
        r1 = filt.process((10, 20))
        r2 = filt.process((20, 40))
        assert r1[0] == 10 and r2[0] != 20
        print(f"  [PASS] Smoothing: {r1} -> {r2}")
    except Exception as exc:
        print(f"  [FAIL] Smoothing: {exc}")
        ok = False

    # 5) One Euro filter
    try:
        from app.virtual_touch.smoothing import OneEuroFilter  # noqa: PLC0415
        oe = OneEuroFilter(min_cutoff=1.0, beta=0.1)
        noisy = [(100 + (i % 3) * 2, 200) for i in range(20)]
        out = [oe.process(p) for p in noisy]
        span = max(p[0] for p in out) - min(p[0] for p in out)
        assert span <= 4.0 and span > 0.0
        print(f"  [PASS] One Euro filter: jitter {max(p[0] for p in noisy) - min(p[0] for p in noisy)}px -> {span:.2f}px")
    except Exception as exc:
        print(f"  [FAIL] One Euro filter: {exc}")
        ok = False

    if ok:
        print("\nAll self-tests passed.")
        return 0
    print("\nSome self-tests FAILED.")
    return 1