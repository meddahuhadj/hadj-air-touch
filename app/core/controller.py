"""Main pipeline controller orchestrating camera -> tracking -> gestures -> input."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from app.core.events import Event, EventBus, EventType
from app.core.state import AppState, AppStatus, Mode
from app.config import Settings
from app.services.telemetry import Telemetry
from app.calibration.calibrator import CalibState
from app.virtual_touch.smoothing import OneEuroFilter

if TYPE_CHECKING:
    from app.camera.capture import CameraCapture
    from app.tracking.hand_tracker import HandTracker
    from app.gestures.engine import GestureEngine
    from app.virtual_touch.engine import VirtualTouchEngine

_LOG = logging.getLogger(__name__)


class PipelineController:
    """Orchestrates the full processing loop in a background thread."""

    def __init__(self, bus: EventBus, settings: Settings) -> None:
        self.bus = bus
        self.settings = settings
        self.state = AppState()
        self.telemetry = Telemetry()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Lazy-initialised components (injected after construction)
        self._camera: CameraCapture | None = None
        self._tracker: HandTracker | None = None
        self._gesture_engine: GestureEngine | None = None
        self._vt_engine: VirtualTouchEngine | None = None
        self._calibrator: Any = None
        self._quality_mon: Any = None

        self._last_frame_time: float = 0.0
        self._last_cursor_pos: Any = None
        self._hand_was_visible: bool = False
        self._one_euro: OneEuroFilter | None = None

        # Subscribe to emergency stop
        self.bus.subscribe(EventType.EMERGENCY_STOP, self._on_emergency)

        # Injected lazily
        self._dispatcher: Any = None
        self._screen_mgr: Any = None
        self._position_sink: Any = None

    # -- component injection --

    def set_camera(self, cam: CameraCapture) -> None:
        self._camera = cam

    def set_tracker(self, tracker: HandTracker) -> None:
        self._tracker = tracker

    def set_gesture_engine(self, ge: GestureEngine) -> None:
        self._gesture_engine = ge

    def set_virtual_touch_engine(self, vte: VirtualTouchEngine) -> None:
        self._vt_engine = vte

    def set_calibrator(self, calibrator: Any) -> None:
        """Set the calibration workflow so the pipeline can feed hand points."""
        self._calibrator = calibrator

    def set_quality_monitor(self, monitor: Any) -> None:
        """Set the tracking quality monitor (evaluated every frame)."""
        self._quality_mon = monitor

    def set_dispatcher(self, dispatcher: Any) -> None:
        """Set an InputDispatcher for Windows input actions."""
        self._dispatcher = dispatcher

    def set_screen_manager(self, sm: Any) -> None:
        self._screen_mgr = sm

    def set_position_sink(self, sink: Any) -> None:
        """Register a callable receiving the latest cursor position (for HUDs)."""
        self._position_sink = sink

    def _publish_position(self, pos: tuple[float, float]) -> None:
        if self._position_sink is None:
            return
        try:
            self._position_sink(pos)
        except Exception:  # pragma: no cover - defensive
            _LOG.debug("Position sink call failed", exc_info=True)

    # -- lifecycle --

    @property
    def is_running(self) -> bool:
        """Whether the pipeline's background thread is currently alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self.state.update(camera_active=True, tracking_active=True)
        # Preserve CALIBRATING if the pipeline was started for calibration.
        if self.state.status != AppStatus.CALIBRATING:
            self.state.update(status=AppStatus.RUNNING)
        self.bus.emit_simple(EventType.STATE_CHANGED, status=self.state.status.value)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pipeline")
        self._thread.start()
        _LOG.info("Pipeline started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.state.update(status=AppStatus.IDLE, camera_active=False, tracking_active=False)
        self.bus.emit_simple(EventType.STATE_CHANGED, status=AppStatus.IDLE.value)
        _LOG.info("Pipeline stopped")

    def pause(self) -> None:
        self.state.update(status=AppStatus.PAUSED, tracking_active=False)
        self.bus.emit_simple(EventType.STATE_CHANGED, status=AppStatus.PAUSED.value)

    def resume(self) -> None:
        self.state.update(status=AppStatus.RUNNING, tracking_active=True)
        self.bus.emit_simple(EventType.STATE_CHANGED, status=AppStatus.RUNNING.value)

    def _on_emergency(self, _event: Event) -> None:
        self.pause()
        _LOG.warning("Emergency stop triggered")

    def _feed_calibration(self, hand: Any) -> None:
        """Feed the current fingertip position to the calibration workflow.

        The Calibrator itself enforces the "hold for ~1 s" requirement, so we
        can simply publish the fingertip every frame. Emits CALIBRATION_STEP /
        CALIBRATION_COMPLETE / CALIBRATION_FAILED when corners are recorded.
        """
        cal = self._calibrator
        if cal is None:
            return
        tip = hand.index_finger_tip
        if tip is None:
            return
        recording = (
            cal.state in (
                CalibState.TOP_LEFT,
                CalibState.TOP_RIGHT,
                CalibState.BOTTOM_RIGHT,
                CalibState.BOTTOM_LEFT,
            )
        )
        try:
            completed = cal.feed_point(tip) if recording else False
        except Exception as exc:  # pragma: no cover - defensive
            _LOG.exception("Calibration feed failed: %s", exc)
            return
        if completed:
            self.bus.emit_simple(
                EventType.CALIBRATION_STEP,
                corner=max(0, cal.step - 1),
                point=tip,
            )
            if cal.state == CalibState.DONE:
                self.bus.emit_simple(EventType.CALIBRATION_COMPLETE, result=cal.result)
            elif cal.state == CalibState.FAILED:
                self.bus.emit_simple(
                    EventType.CALIBRATION_FAILED, message=cal.result.message)

    # -- main loop --

    def _loop(self) -> None:
        cam = self._camera
        tracker = self._tracker
        if cam is None or tracker is None:
            _LOG.error("Pipeline cannot start: camera or tracker not set")
            return

        while not self._stop_event.is_set():
            if self.state.status not in (AppStatus.RUNNING, AppStatus.CALIBRATING):
                time.sleep(0.05)
                continue

            t0 = time.perf_counter()

            frame = cam.grab()
            if frame is None:
                time.sleep(0.005)
                continue

            hand_data = tracker.process_frame(frame)

            now = time.perf_counter()
            self.telemetry.update_frame(now)

            if hand_data is None:
                self.state.update(hands_detected=0)
                self.bus.emit_simple(EventType.HAND_LOST)
                if self._hand_was_visible:
                    _LOG.info("Hand lost")
                    self._hand_was_visible = False
                continue

            if not self._hand_was_visible:
                _LOG.info("Hand detected (confidence=%.2f)", hand_data.confidence)
                self._hand_was_visible = True

            self.state.update(
                hands_detected=1,
                confidence=hand_data.confidence,
            )

            self.bus.emit_simple(
                EventType.HAND_DETECTED,
                hand=hand_data,
            )

            if self.state.status == AppStatus.CALIBRATING:
                self._feed_calibration(hand_data)
            else:
                # Tracking quality scoring while actually tracking
                if self._quality_mon is not None:
                    rep = self._quality_mon.evaluate(hand_data)
                    self.state.stats.tracking_quality = rep.level.value

                # Cursor control (Air Mouse mode): map fingertip -> screen -> move cursor
                if (
                    self.state.mode == Mode.AIR_MOUSE
                    and self._dispatcher is not None
                    and hand_data.index_finger_tip is not None
                ):
                    self._move_cursor(hand_data)

                # Gesture engine
                if self._gesture_engine:
                    gesture = self._gesture_engine.update(hand_data, now)
                    if gesture:
                        gesture_name = gesture.name.name  # GestureResult.name is a GestureType enum
                        self.state.update(gesture=gesture_name)
                        self.bus.emit_simple(
                            EventType.GESTURE_DETECTED,
                            gesture=gesture,
                            hand=hand_data,
                        )
                        self._dispatch_action(gesture_name, hand_data)

                # Virtual touch engine
                if self._vt_engine and self.state.mode == Mode.VIRTUAL_TOUCH:
                    vt = self._vt_engine
                    touching = vt.is_virtual_touch(hand_data)
                    finger_pos = hand_data.index_finger_tip
                    screen_pos = None
                    if finger_pos is not None and self._dispatcher is not None:
                        if self._screen_mgr is not None:
                            size = self._screen_mgr.get_screen_size(
                                self.settings.config.monitor)
                        else:
                            size = (1920, 1080)
                        screen_pos = self._dispatcher.map_fingertip_to_screen(finger_pos, size)

                    vt.update(
                        touching=touching,
                        finger_on_screen=finger_pos is not None,
                        elapsed_ms=(now - self._last_frame_time) * 1000,
                        position=screen_pos,
                    )
                    self._handle_touch_action(vt, screen_pos)

            self._last_frame_time = now

            # Enforce target FPS
            dt = time.perf_counter() - t0
            target = 1.0 / max(self.settings.config.camera.fps, 1)
            if dt < target:
                time.sleep(target - dt)

    def _dispatch_action(self, gesture_name: str, hand_data: Any) -> None:
        """Translate a recognised gesture into a Windows input action.

        Delegates to the InputDispatcher (which owns the profile lookup).
        Pause/resume are pipeline-level and handled directly.
        """
        if gesture_name in ("OPEN_PALM", "PAUSE"):
            self.pause()
            return
        if gesture_name == "WAVE":
            # Wave toggles interaction: pause if running, resume if paused.
            if self.state.status == AppStatus.RUNNING:
                self.pause()
            elif self.state.status == AppStatus.PAUSED:
                self.resume()
            return
        if gesture_name == "RESUME":
            self.resume()
            return
        if self._dispatcher is not None:
            self._dispatcher.handle_gesture(gesture_name.lower())

    def _move_cursor(self, hand_data: Any) -> None:
        """Map the index fingertip to screen coords and move the cursor."""
        tip = hand_data.index_finger_tip
        if tip is None or self._dispatcher is None:
            return
        if self._screen_mgr is not None:
            size = self._screen_mgr.get_screen_size(self.settings.config.monitor)
        else:
            size = (1920, 1080)

        target = self._dispatcher.map_fingertip_to_screen(tip, size)
        cur = self.settings.config

        # Optional One Euro filter: low-latency jitter reduction on the raw
        # mapped target, before sensitivity/smoothing are applied.
        if cur.cursor.one_euro:
            if self._one_euro is None:
                self._one_euro = OneEuroFilter(
                    min_cutoff=cur.cursor.one_euro_min_cutoff,
                    beta=cur.cursor.one_euro_beta,
                )
            target = self._one_euro.process(target, time.perf_counter())
        else:
            self._one_euro = None

        pos = self._dispatcher.apply_cursor_settings(
            target,
            self._last_cursor_pos or target,
            speed=cur.cursor.speed,
            smoothing=cur.cursor.smoothing,
            acceleration=cur.cursor.acceleration,
            dead_zone=cur.cursor.dead_zone,
            screen_height=size[1],
            screen_size=(size[0], size[1]),
        )
        self._last_cursor_pos = pos
        self._publish_position(pos)
        try:
            self._dispatcher.mouse.move_smoothed(pos)
        except Exception as exc:
            _LOG.debug("Cursor move skipped: %s", exc)

    def _handle_touch_action(self, vt: Any, screen_pos: Any) -> None:
        """Route virtual-touch engine actions to the dispatcher."""
        if self._dispatcher is None:
            return
        action = vt.action
        if action == "tap":
            if vt.is_virtual_touch_active and screen_pos is not None:
                self._dispatcher.mouse.set_position(screen_pos[0], screen_pos[1])
                self._publish_position(screen_pos)
            self._dispatcher.mouse.left_click()
        elif action == "long_press":
            self._dispatcher.mouse.mouse_down("left")
        elif action == "long_press_end":
            self._dispatcher.mouse.mouse_up("left")
        elif action == "drag_start":
            pos = screen_pos or self._last_cursor_pos
            if pos is not None:
                self._dispatcher.mouse.drag_start(pos[0], pos[1])
        elif action == "drag_end":
            self._dispatcher.mouse.drag_end()
        elif vt.drag_delta is not None and self._last_cursor_pos is not None:
            # Drag while moving: move the cursor with smoothing
            base = self._last_cursor_pos
            pos = (
                base[0] + vt.drag_delta[0] * 100,
                base[1] + vt.drag_delta[1] * 100,
            )
            self._last_cursor_pos = pos
            self._dispatcher.mouse.move_smoothed(pos)