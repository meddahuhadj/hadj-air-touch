"""Main application window – Windows 11-inspired dashboard."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QCheckBox,
    QLineEdit,
    QGroupBox,
)

from app.ui.theme import apply_theme, Theme, DARK_CARD, DARK_BORDER, DARK_SUCCESS, DARK_WARNING
from app.ui.widgets import (
    Card,
    StatusRow,
    PrimaryButton,
    SecondaryButton,
    DangerButton,
    SliderRow,
    SectionHeader,
)
from app.core.events import Event, EventBus, EventType
from app.core.state import AppStatus
from app.core.controller import PipelineController
from app.calibration.calibrator import Calibrator, CalibState
from app.tracking.hand_tracker import HandTracker
from app.tracking.quality import TrackingQualityMonitor, QualityLevel
from app.gestures.engine import GestureEngine
from app.virtual_touch.engine import VirtualTouchEngine
from app.windows_input.mouse import MouseController
from app.windows_input.keyboard import KeyboardController
from app.windows_input.screen import ScreenManager
from app.windows_input.dispatcher import InputDispatcher
from app.ui.overlay_keyboard import OverlayKeyboard
from app.camera.manager import CameraManager
from app.camera.capture import CameraCapture
from app.privacy.guard import PrivacyGuard
from app.privacy.tray import TrayController
from app.profiles.manager import ProfileManager
from app.assistant.hadj_ai import HadjAI
from app.config import Settings
from app.voice.controller import VoiceController

_LOG = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level window with sidebar navigation and stacked page views."""

    def __init__(self, args: argparse.Namespace | None = None) -> None:
        super().__init__()
        self.args = args
        self.setWindowTitle("HADJ AIR TOUCH")
        self.setMinimumSize(1100, 720)

        # Core components
        self.bus = EventBus()
        self.settings = Settings()
        self.camera_manager = CameraManager()
        self.camera_index = self.settings.config.camera.index
        self.camera = CameraCapture(
            camera_index=self.settings.config.camera.index,
            width=self.settings.config.camera.width,
            height=self.settings.config.camera.height,
            fps=self.settings.config.camera.fps,
            mirror=self.settings.config.camera.mirror,
        )
        self.tracker = HandTracker()
        self.gesture_engine = GestureEngine()
        for name, enabled in self.settings.config.gestures.items():
            self.gesture_engine.configured_gestures[name] = enabled
        self.vt_engine = VirtualTouchEngine()
        self.mouse_ctrl = MouseController()
        self.kb_ctrl = KeyboardController()
        self.keyboard_overlay = OverlayKeyboard()
        self.keyboard_overlay.keyPressed.connect(self._on_overlay_key)
        self.screen_mgr = ScreenManager()
        primary = self.screen_mgr.primary
        sw, sh = (primary.width, primary.height) if primary else (1920, 1080)
        self.calibrator = Calibrator(screen_width=sw, screen_height=sh)
        self.privacy = PrivacyGuard(self.bus)
        self.profiles = ProfileManager()
        self.quality_mon = TrackingQualityMonitor()
        self.ai = HadjAI()
        self.voice = VoiceController(self.bus, language=self.settings.config.language)
        self.voice.set_command_callback(self._on_voice_command)
        self.bus.subscribe(EventType.CALIBRATION_STARTED, lambda _e: self._on_calib_start())
        self.pipeline = PipelineController(self.bus, self.settings)
        self.pipeline.set_camera(self.camera)
        self.pipeline.set_tracker(self.tracker)
        self.pipeline.set_gesture_engine(self.gesture_engine)
        self.pipeline.set_virtual_touch_engine(self.vt_engine)
        self.pipeline.set_screen_manager(self.screen_mgr)
        self.pipeline.set_calibrator(self.calibrator)
        self.pipeline.set_quality_monitor(self.quality_mon)

        # Apply the user-facing virtual-touch settings to the engine
        vt_cfg = self.settings.config.virtual_touch
        self.vt_engine.apply_settings(
            touch_depth_cm=vt_cfg.touch_depth_cm,
            sensitivity=vt_cfg.sensitivity,
        )

        # Input dispatcher – connects events to real Windows input
        self.dispatcher = InputDispatcher(
            self.bus, self.mouse_ctrl, self.kb_ctrl, self.calibrator, self.settings,
        )
        self.pipeline.set_dispatcher(self.dispatcher)

        self._build_ui()
        self._connect_signals()
        self._apply_theme()

        self.tray = TrayController()
        self.tray.install(self)

        self._last_hand = None
        self._last_gesture_event_ts = 0.0

        # Periodic status refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(500)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(220)
        self._sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {DARK_CARD};
                border-right: 1px solid {DARK_BORDER};
            }}
        """)
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(4)

        # App title
        title = QLabel("HADJ\nAIR TOUCH")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: 1px; margin-bottom: 16px;")
        sb_layout.addWidget(title)

        self._nav_buttons: list[QPushButton] = []  # type: ignore[name-defined]
        pages = [
            ("Dashboard", 0),
            ("Calibration", 1),
            ("Gestures", 2),
            ("Camera", 3),
            ("Profiles", 4),
            ("Keyboard", 5),
            ("Settings", 6),
            ("Privacy", 7),
            ("Voice", 8),
        ]
        for label, idx in pages:
            btn = SecondaryButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked, i=idx: self._stack.setCurrentIndex(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sb_layout.addStretch()
        ver = QLabel("v1.0.0")
        ver.setStyleSheet("color: #888; font-size: 11px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb_layout.addWidget(ver)

        main_layout.addWidget(self._sidebar)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._dashboard_page())
        self._stack.addWidget(self._calibration_page())
        self._stack.addWidget(self._gestures_page())
        self._stack.addWidget(self._camera_page())
        self._stack.addWidget(self._profiles_page())
        self._stack.addWidget(self._keyboard_page())
        self._stack.addWidget(self._settings_page())
        self._stack.addWidget(self._privacy_page())
        self._stack.addWidget(self._voice_page())
        main_layout.addWidget(self._stack, 1)
        self._stack.currentChanged.connect(self._on_page_changed)

    def _make_scrollable(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    # ---- Pages ----

    def _dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        header = QLabel("HADJ AIR TOUCH")
        header.setObjectName("Title")
        layout.addWidget(header)

        subtitle = QLabel("AI-powered virtual touch interface for Windows")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        # Status card
        card = Card("System Status")
        self._status_camera = StatusRow("Camera")
        self._status_tracking = StatusRow("Hand Tracking")
        self._status_touch = StatusRow("Virtual Touch")
        self._status_fps = StatusRow("FPS")
        self._status_latency = StatusRow("Latency")
        self._status_quality = StatusRow("Tracking Quality")
        self._status_gesture = StatusRow("Gesture")

        for row in [self._status_camera, self._status_tracking, self._status_touch,
                     self._status_fps, self._status_latency, self._status_quality,
                     self._status_gesture]:
            card.card_layout.addWidget(row)
        layout.addWidget(card)

        # Controls card
        ctrl = Card("Controls")
        btn_row = QHBoxLayout()
        self._btn_start = PrimaryButton("START")
        self._btn_pause = SecondaryButton("PAUSE")
        self._btn_calibrate = SecondaryButton("CALIBRATE")
        self._btn_exit = DangerButton("STOP CAMERA")

        self._btn_start.clicked.connect(self._on_start)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_calibrate.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        self._btn_exit.clicked.connect(self._on_exit)

        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_pause)
        btn_row.addWidget(self._btn_calibrate)
        btn_row.addWidget(self._btn_exit)
        ctrl.card_layout.addLayout(btn_row)
        layout.addWidget(ctrl)

        # Quick tips
        tips = Card("Quick Start")
        tips.card_layout.addWidget(QLabel(
            "1. Click START to begin tracking\n"
            "2. Point your index finger to move the cursor\n"
            "3. Pinch (thumb + index) to click\n"
            "4. Run CALIBRATE for virtual touch mode\n"
            "5. Press Ctrl+Alt+H to emergency stop"
        ))
        layout.addWidget(tips)

        layout.addStretch()
        return page

    def _calibration_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Screen Calibration"))
        layout.addWidget(QLabel("Point your finger at each corner of the screen and hold steady."))

        card = Card("Calibration Progress")
        self._calib_status = QLabel("Ready")
        self._calib_status.setObjectName("Title")
        card.card_layout.addWidget(self._calib_status)
        self._calib_quality = QLabel("")
        card.card_layout.addWidget(self._calib_quality)
        self._calib_instruction = QLabel("")
        card.card_layout.addWidget(self._calib_instruction)
        layout.addWidget(card)

        btn_row = QHBoxLayout()
        self._calib_start = PrimaryButton("START CALIBRATION")
        self._calib_start.clicked.connect(self._on_calib_start)
        btn_row.addWidget(self._calib_start)
        self._calib_skip = SecondaryButton("SKIP POINT")
        self._calib_skip.clicked.connect(self._on_calib_skip)
        btn_row.addWidget(self._calib_skip)
        self._calib_reset = SecondaryButton("RESET")
        self._calib_reset.clicked.connect(self._on_calib_reset)
        btn_row.addWidget(self._calib_reset)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("Screen Mode:"))
        self._touch_mode_combo = QComboBox()
        self._touch_mode_combo.addItems(["Air Mouse", "Virtual Touch"])
        self._touch_mode_combo.setCurrentIndex(
            1 if self.settings.config.mode == "virtual_touch" else 0)
        self._touch_mode_combo.currentIndexChanged.connect(self._on_mode_change)
        layout.addWidget(self._touch_mode_combo)

        layout.addStretch()
        return page

    def _gestures_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Gesture Configuration"))

        card = Card("Active Gestures")
        self._gesture_checks: dict[str, QCheckBox] = {}
        gestures = ["point", "pinch", "double_pinch", "right_click", "grab",
                     "open_palm", "fist", "swipe", "zoom", "peace", "thumbs_up", "wave"]
        for g in gestures:
            cb = QCheckBox(g.replace("_", " ").title())
            cb.setChecked(self.gesture_engine.configured_gestures.get(g, False))
            cb.stateChanged.connect(lambda state, name=g: self._on_gesture_toggle(name, state))
            card.card_layout.addWidget(cb)
            self._gesture_checks[g] = cb
        layout.addWidget(card)

        card2 = Card("Gesture Reference")
        card2.card_layout.addWidget(QLabel(
            "POINT: Index finger extended, others folded → Move cursor\n"
            "PINCH: Thumb + index tips together → Left click\n"
            "DOUBLE PINCH: Two rapid pinches → Double click\n"
            "RIGHT CLICK: Thumb + middle finger → Right click\n"
            "GRAB: All fingers closed → Drag mode\n"
            "OPEN PALM: All five fingers spread → Pause\n"
            "SWIPE: Quick horizontal/vertical movement → Page nav/scroll\n"
            "ZOOM: Two-finger pinch in/out → Zoom\n"
            "THUMBS UP: Thumb up, other fingers folded → Volume up / context action\n"
            "WAVE: Rapid hand waving → Pause / resume interaction\n"
        ))
        layout.addWidget(card2)

        layout.addStretch()
        return page

    def _camera_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Camera Settings"))

        card = Card("Camera Selection")
        self._cam_combo = QComboBox()
        for cam in self.camera_manager.cameras:
            self._cam_combo.addItem(f"{cam.name} ({cam.width}x{cam.height} @ {cam.fps}fps)", cam.index)
        card.card_layout.addWidget(self._cam_combo)
        self._cam_combo.currentIndexChanged.connect(self._on_camera_change)

        self._cam_mirror = QCheckBox("Mirror mode")
        self._cam_mirror.setChecked(self.settings.config.camera.mirror)
        self._cam_mirror.toggled.connect(self._on_mirror_toggle)
        card.card_layout.addWidget(self._cam_mirror)
        layout.addWidget(card)

        card2 = Card("Resolution & Quality")
        cam_cfg = self.settings.config.camera
        self._cam_width = SliderRow("Width", 320, 1920, cam_cfg.width, 0)
        self._cam_height = SliderRow("Height", 240, 1080, cam_cfg.height, 0)
        self._cam_fps = SliderRow("FPS", 15, 60, cam_cfg.fps, 0)
        card2.card_layout.addWidget(self._cam_width)
        card2.card_layout.addWidget(self._cam_height)
        card2.card_layout.addWidget(self._cam_fps)
        layout.addWidget(card2)

        apply_btn = PrimaryButton("APPLY CAMERA SETTINGS")
        apply_btn.clicked.connect(self._on_apply_camera_settings)
        layout.addWidget(apply_btn)

        card3 = Card("Camera Preview")
        self._cam_preview_label = QLabel("Preview not available (camera not started)")
        self._cam_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_preview_label.setMinimumHeight(200)
        card3.card_layout.addWidget(self._cam_preview_label)
        layout.addWidget(card3)

        layout.addStretch()
        return page

    def _profiles_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Interaction Profiles"))

        card = Card("Active Profile")
        self._profile_combo = QComboBox()
        self._profile_combo.addItems(self.profiles.all_names)
        self._profile_combo.setCurrentText(self.profiles.active_name)
        self._profile_combo.currentTextChanged.connect(self._on_profile_change)
        card.card_layout.addWidget(self._profile_combo)
        self._profile_desc = QLabel(self.profiles.get_active().description)
        card.card_layout.addWidget(self._profile_desc)
        layout.addWidget(card)

        card2 = Card("Available Profiles")
        for name in self.profiles.all_names:
            p = self.profiles.get_profile(name)
            if p:
                row = QLabel(f"{p.name}: {p.description}")
                card2.card_layout.addWidget(row)
        layout.addWidget(card2)

        layout.addStretch()
        return page

    def _keyboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Virtual Keyboard"))
        layout.addWidget(QLabel("The on-screen keyboard allows typing without a physical keyboard."))

        card = Card("Layout")
        self._kb_layout_combo = QComboBox()
        from app.keyboard.virtual_keyboard import KeyboardLayout
        for kl in KeyboardLayout:
            self._kb_layout_combo.addItem(kl.value, kl)
        self._kb_layout_combo.currentIndexChanged.connect(
            lambda _i: self.keyboard_overlay.set_layout(self._kb_layout_combo.currentData()))
        card.card_layout.addWidget(self._kb_layout_combo)
        layout.addWidget(card)

        card2 = Card("Keyboard Preview")
        preview = QLabel(
            "The virtual keyboard appears as an overlay when enabled.\n"
            "Point at a key and pinch to type.\n\n"
            "Supported layouts:\n"
            "  • QWERTY (English)\n"
            "  • AZERTY (French)\n"
            "  • Arabic\n"
            "  • Numbers & Symbols\n"
            "  • Emoji"
        )
        card2.card_layout.addWidget(preview)
        layout.addWidget(card2)

        card3 = Card("Overlay")
        self._kb_overlay_btn = PrimaryButton("SHOW OVERLAY KEYBOARD")
        self._kb_overlay_btn.clicked.connect(self._on_kb_overlay_toggle)
        card3.card_layout.addWidget(self._kb_overlay_btn)
        info = QLabel(
            "The overlay floats above your screen and never steals focus,\n"
            "so typed text lands in the app below the cursor."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#888;")
        card3.card_layout.addWidget(info)
        layout.addWidget(card3)

        layout.addStretch()
        return page

    def _voice_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Voice Control"))
        layout.addWidget(QLabel("Speak commands to control the cursor, scrolling, media and more."))

        card = Card("Voice Engine")
        row = QHBoxLayout()
        self._voice_status = QLabel("Stopped")
        self._voice_status.setStyleSheet(f"color:{DARK_WARNING}; font-weight:600;")
        row.addWidget(self._voice_status)
        row.addStretch()
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language:"))
        self._voice_lang_combo = QComboBox()
        self._voice_lang_combo.addItems(["English", "Fran\u00e7ais", "Arabic"])
        cur = ["en", "fr", "ar"].index(self.settings.config.language)
        self._voice_lang_combo.setCurrentIndex(max(0, cur))
        self._voice_lang_combo.currentIndexChanged.connect(self._on_voice_language_change)
        lang_row.addWidget(self._voice_lang_combo)
        lang_row.addStretch()
        card.card_layout.addLayout(row)
        card.card_layout.addLayout(lang_row)
        layout.addWidget(card)

        card2 = Card("Start / Stop")
        self._voice_button = PrimaryButton("START VOICE")
        self._voice_button.clicked.connect(self._on_voice_toggle)
        card2.card_layout.addWidget(self._voice_button)
        layout.addWidget(card2)

        card3 = Card("Recognized Commands")
        commands = QLabel(
            "\u2022 \"click\", \"double click\", \"right click\"\n"
            "\u2022 \"scroll up\" / \"scroll down\"\n"
            "\u2022 \"pause\" / \"resume\"\n"
            "\u2022 \"volume up\" / \"volume down\" / \"mute\"\n"
            "\u2022 \"play\" / \"next\" / \"previous\"\n"
            "\u2022 \"calibrate\" / \"close window\" / \"open browser\"")
        commands.setWordWrap(True)
        commands.setStyleSheet("color:#bbb;")
        card3.card_layout.addWidget(commands)
        layout.addWidget(card3)

        layout.addStretch()
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Settings"))

        cursor_cfg = self.settings.config.cursor
        card = Card("Cursor")
        self._cursor_speed = SliderRow("Cursor Speed", 0.1, 3.0, cursor_cfg.speed)
        self._cursor_smoothing = SliderRow("Cursor Smoothing", 0.0, 1.0, cursor_cfg.smoothing, 2)
        self._cursor_speed.valueChanged.connect(self._on_cursor_speed_change)
        self._cursor_smoothing.valueChanged.connect(self._on_cursor_smoothing_change)
        card.card_layout.addWidget(self._cursor_speed)
        card.card_layout.addWidget(self._cursor_smoothing)
        layout.addWidget(card)

        vt_cfg = self.settings.config.virtual_touch
        card2 = Card("Virtual Touch")
        self._touch_depth = SliderRow("Touch Depth (cm)", 1.0, 10.0, vt_cfg.touch_depth_cm)
        self._touch_sensitivity = SliderRow("Sensitivity", 0.5, 2.0, vt_cfg.sensitivity, 2)
        self._touch_depth.valueChanged.connect(self._on_touch_depth_change)
        self._touch_sensitivity.valueChanged.connect(self._on_touch_sensitivity_change)
        card2.card_layout.addWidget(self._touch_depth)
        card2.card_layout.addWidget(self._touch_sensitivity)
        layout.addWidget(card2)

        card3 = Card("Interaction Distance")
        self._interaction_dist = SliderRow(
            "Distance (cm)", 20, 120, vt_cfg.interaction_distance_cm, 0)
        self._interaction_dist.valueChanged.connect(self._on_interaction_dist_change)
        card3.card_layout.addWidget(self._interaction_dist)
        layout.addWidget(card3)

        card4 = Card("Safety")
        self._auto_timeout = QCheckBox("Auto-pause after 1 hour")
        self._auto_timeout.setChecked(self.settings.config.safety.auto_timeout_sec > 0)
        self._auto_timeout.toggled.connect(self._on_auto_timeout_toggle)
        card4.card_layout.addWidget(self._auto_timeout)
        self._false_click = QCheckBox("False-click prevention")
        self._false_click.setChecked(self.settings.config.safety.false_click_guard)
        self._false_click.toggled.connect(self._on_false_click_toggle)
        card4.card_layout.addWidget(self._false_click)
        layout.addWidget(card4)

        card4b = Card("Startup")
        self._auto_start_chk = QCheckBox("Start HADJ AIR TOUCH with Windows")
        self._auto_start_chk.setChecked(self.settings.config.auto_start)
        self._auto_start_chk.toggled.connect(self._on_auto_start_toggle)
        card4b.card_layout.addWidget(self._auto_start_chk)
        layout.addWidget(card4b)

        card5 = Card("Language & Theme")
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English", "Fran\u00e7ais", "Arabic"])
        languages = {"en": "English", "fr": "Fran\u00e7ais", "ar": "Arabic"}
        self._lang_combo.setCurrentText(languages.get(self.settings.config.language, "English"))
        self._lang_combo.currentTextChanged.connect(self._on_language_change)
        card5.card_layout.addWidget(QLabel("Language"))
        card5.card_layout.addWidget(self._lang_combo)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light"])
        self._theme_combo.setCurrentText("Dark" if self.settings.config.theme == "dark" else "Light")
        card5.card_layout.addWidget(QLabel("Theme"))
        card5.card_layout.addWidget(self._theme_combo)
        self._theme_combo.currentTextChanged.connect(self._on_theme_change)
        layout.addWidget(card5)

        layout.addStretch()
        return page

    def _privacy_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Privacy & Security"))

        card = Card("Privacy Statement")
        card.card_layout.addWidget(QLabel(self.privacy.privacy_statement()))
        layout.addWidget(card)

        card2 = Card("Emergency Stop")
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Hotkey:"))
        self._emergency_hotkey_edit = QLineEdit(self.settings.config.safety.emergency_hotkey)
        self._emergency_hotkey_edit.setMaximumWidth(160)
        self._emergency_hotkey_edit.textChanged.connect(self._on_emergency_hotkey_change)
        hotkey_row.addWidget(self._emergency_hotkey_edit)
        hotkey_row.addWidget(QLabel("e.g. Ctrl+Alt+H / F12 / Ctrl+Shift+Q"))
        hotkey_row.addStretch()
        card2.card_layout.addLayout(hotkey_row)
        card2.card_layout.addWidget(QLabel(
            "Press the hotkey at any time to immediately disable all interaction.\n"
            "The camera and tracking will pause."
        ))
        self._emergency_btn = DangerButton("TRIGGER EMERGENCY STOP")
        self._emergency_btn.clicked.connect(self._on_emergency)
        card2.card_layout.addWidget(self._emergency_btn)
        layout.addWidget(card2)

        card3 = Card("Camera Control")
        self._cam_stop_btn = DangerButton("STOP CAMERA NOW")
        self._cam_stop_btn.clicked.connect(self._on_exit)
        card3.card_layout.addWidget(self._cam_stop_btn)
        layout.addWidget(card3)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.bus.subscribe(EventType.HAND_DETECTED, self._on_hand_detected)
        self.bus.subscribe(EventType.HAND_LOST, self._on_hand_lost)
        self.bus.subscribe(EventType.GESTURE_DETECTED, self._on_gesture_detected)
        self.bus.subscribe(EventType.EMERGENCY_STOP, lambda e: self._on_emergency())
        self.bus.subscribe(EventType.STATE_CHANGED, lambda e: self._refresh_status())
        self.bus.subscribe(EventType.CALIBRATION_STEP, self._on_calibration_step)
        self.bus.subscribe(EventType.CALIBRATION_COMPLETE, self._on_calibration_complete)
        self.bus.subscribe(EventType.CALIBRATION_FAILED, self._on_calibration_failed)

    def _apply_theme(self) -> None:
        apply_theme(dark=True)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        self._start_engine()
        self._refresh_status()
        _LOG.info("Pipeline started from UI")

    def _start_engine(self) -> None:
        """Open the camera, start capture and run the pipeline."""
        if self.pipeline.is_running:
            return
        self.camera.open()
        self.camera.start()
        self.privacy.notify_camera_active()
        self.privacy.start_hotkey_listener(self.settings.config.safety.emergency_hotkey)
        self.pipeline.start()

    def _on_pause(self) -> None:
        if self.pipeline.state.status == AppStatus.RUNNING:
            self.pipeline.pause()
        else:
            self.pipeline.resume()
        self._refresh_status()

    def _open_settings_page(self) -> None:
        self._stack.setCurrentIndex(6)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_exit(self) -> None:
        self.pipeline.stop()
        self.camera.stop()
        self.privacy.notify_camera_inactive()
        self.privacy.stop_hotkey_listener()
        self._refresh_status()

    def _on_emergency(self) -> None:
        self.pipeline.pause()
        QMessageBox.information(self, "Emergency Stop",
                                "All interaction has been paused.\nPress Resume to continue.")

    def _on_emergency_hotkey_change(self, text: str) -> None:
        hotkey = text.strip() or "Ctrl+Alt+H"
        from app.privacy.guard import parse_hotkey
        if not parse_hotkey(hotkey):
            self._emergency_hotkey_edit.setStyleSheet("border:1px solid #e81123;")
            return
        self._emergency_hotkey_edit.setStyleSheet("")
        self.settings.set("safety.emergency_hotkey", hotkey)
        self.privacy.stop_hotkey_listener()
        self.privacy.start_hotkey_listener(hotkey)

    def _on_calib_start(self) -> None:
        # Calibration needs live hand data, so ensure the engine is running.
        self._start_engine()
        self.calibrator.start()
        name, pos = self.calibrator.get_current_corner()
        self._calib_instruction.setText(
            f"Point your finger at the TOP LEFT corner and hold steady.\n"
            f"({pos[0]}, {pos[1]})"
        )
        self._calib_status.setText("Calibrating...")
        self._calib_quality.setText("")
        self.pipeline.state.update(status=AppStatus.CALIBRATING)

    def _on_calib_skip(self) -> None:
        self.calibrator.skip_current()
        self._update_calib_display()

    def _on_calib_reset(self) -> None:
        self.calibrator.reset()
        self._calib_status.setText("Ready")
        self._calib_quality.setText("")
        self._calib_instruction.setText("")
        self._restore_status_after_calibration()

    def _on_calibration_step(self, event: Event) -> None:
        self._update_calib_display()

    def _on_calibration_complete(self, event: Event) -> None:
        self._update_calib_display()
        result = event.data.get("result")
        if result is not None and result.quality >= 0.5:
            self._status_touch.update("good", "Virtual Touch")
        _LOG.info("Calibration completed from pipeline")

    def _on_calibration_failed(self, event: Event) -> None:
        self._update_calib_display()
        _LOG.warning("Calibration failed: %s", event.data.get("message", ""))

    def _update_calib_display(self) -> None:
        s = self.calibrator.state
        if s == CalibState.COMPUTING:
            self._calib_status.setText("Computing...")
            self._calib_instruction.setText("")
        elif s == CalibState.DONE:
            r = self.calibrator.result
            self._calib_status.setText("Calibration Complete")
            self._calib_quality.setText(f"Quality: {r.quality:.0%} — {r.message}")
            self._restore_status_after_calibration()
        elif s == CalibState.FAILED:
            self._calib_status.setText("Calibration Failed")
            self._calib_quality.setText(self.calibrator.result.message)
            self._restore_status_after_calibration()
        else:
            name, pos = self.calibrator.get_current_corner()
            self._calib_instruction.setText(
                f"Point at: {name.replace('_', ' ').title()} ({pos[0]}, {pos[1]})\n"
                f"Hold steady for 1 second..."
            )

    def _on_page_changed(self, index: int) -> None:
        """Restore pipeline status when leaving the Calibration page.

        Covers abandoning calibration mid-flow (navigating away, Reset)
        without reaching DONE/FAILED, which would otherwise leave the
        status stuck at CALIBRATING - silently freezing hand tracking even
        though the pipeline thread is still running.
        """
        calibration_index = 1
        if index != calibration_index and self.pipeline.state.status == AppStatus.CALIBRATING:
            self._restore_status_after_calibration()

    def _restore_status_after_calibration(self) -> None:
        """Restore the pipeline status once calibration ends.

        Calibration temporarily overwrites AppStatus with CALIBRATING even
        when the pipeline was already running; blindly resetting to IDLE
        afterwards would desync the UI/status from the still-running
        background thread (START would then look unresponsive).
        """
        status = AppStatus.RUNNING if self.pipeline.is_running else AppStatus.IDLE
        self.pipeline.state.update(status=status)

    def _on_mode_change(self, index: int) -> None:
        from app.core.state import Mode
        if index == 0:
            self.pipeline.state.update(mode=Mode.AIR_MOUSE)
            self.settings.set("mode", "air_mouse")
        else:
            self.pipeline.state.update(mode=Mode.VIRTUAL_TOUCH)
            self.settings.set("mode", "virtual_touch")

    def _on_camera_change(self, index: int) -> None:
        cam_idx = self._cam_combo.currentData()
        if cam_idx is None or cam_idx == self.camera_index:
            return
        self.settings.set("camera.index", cam_idx)
        self.camera_index = cam_idx

        # Swap the live capture device so the change takes effect immediately
        # instead of requiring an app restart.
        was_running = self.camera.is_running
        self.camera.stop()
        self.camera = CameraCapture(
            camera_index=cam_idx,
            width=self.settings.config.camera.width,
            height=self.settings.config.camera.height,
            fps=self.settings.config.camera.fps,
            mirror=self.settings.config.camera.mirror,
        )
        self.pipeline.set_camera(self.camera)
        if was_running:
            self.camera.open()
            self.camera.start()
        _LOG.info("Switched to camera %d", cam_idx)

    def _on_gesture_toggle(self, name: str, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.gesture_engine.configure(name, enabled)
        gestures = dict(self.settings.config.gestures)
        gestures[name] = enabled
        self.settings.set("gestures", gestures)

    def _on_profile_change(self, name: str) -> None:
        self.profiles.set_active(name)
        p = self.profiles.get_active()
        if p:
            self._profile_desc.setText(p.description)
            self.settings.set("active_profile", name)

    def _on_theme_change(self, text: str) -> None:
        apply_theme(dark=(text == "Dark"))
        self.settings.set("theme", "dark" if text == "Dark" else "light")

    def _on_language_change(self, text: str) -> None:
        code = {"English": "en", "Fran\u00e7ais": "fr", "Arabic": "ar"}.get(text, "en")
        self.settings.set("language", code)
        if self.voice is not None:
            self.voice.language = code

    def _on_cursor_speed_change(self, value: float) -> None:
        self.settings.set("cursor.speed", value)

    def _on_cursor_smoothing_change(self, value: float) -> None:
        self.settings.set("cursor.smoothing", value)

    def _on_touch_depth_change(self, value: float) -> None:
        self.settings.set("virtual_touch.touch_depth_cm", value)
        self._apply_vt_settings()

    def _on_touch_sensitivity_change(self, value: float) -> None:
        self.settings.set("virtual_touch.sensitivity", value)
        self._apply_vt_settings()

    def _on_interaction_dist_change(self, value: float) -> None:
        self.settings.set("virtual_touch.interaction_distance_cm", value)

    def _on_auto_timeout_toggle(self, checked: bool) -> None:
        self.settings.set("safety.auto_timeout_sec", 3600 if checked else 0)

    def _on_false_click_toggle(self, checked: bool) -> None:
        self.settings.set("safety.false_click_guard", checked)

    def _apply_vt_settings(self) -> None:
        self.vt_engine.apply_settings(
            touch_depth_cm=self._touch_depth.value,
            sensitivity=self._touch_sensitivity.value,
        )

    def _on_mirror_toggle(self, checked: bool) -> None:
        self.settings.set("camera.mirror", checked)
        self.camera.set_mirror(checked)

    def _on_apply_camera_settings(self) -> None:
        """Persist + apply resolution/FPS, restarting capture when needed."""
        w, h, fps = int(self._cam_width.value), int(self._cam_height.value), int(self._cam_fps.value)
        self.settings.update_section("camera", {"width": w, "height": h, "fps": fps})
        was_running = self.camera.is_running
        self.camera.stop()
        self.camera = CameraCapture(
            camera_index=self.camera_index,
            width=w,
            height=h,
            fps=fps,
            mirror=self.settings.config.camera.mirror,
        )
        self.pipeline.set_camera(self.camera)
        if was_running:
            self.camera.open()
            self.camera.start()
        _LOG.info("Applied camera settings %dx%d @ %dfps", w, h, fps)

    def _on_kb_overlay_toggle(self) -> None:
        self.keyboard_overlay.set_layout(self._kb_layout_combo.currentData())
        self.keyboard_overlay.toggle()

    def _on_overlay_key(self, code: str, label: str) -> None:
        try:
            self.kb_ctrl.press_key(code)
        except Exception as exc:  # noqa: BLE001
            _LOG.error("Failed to inject key %r: %s", label, exc)

    def _on_voice_command(self, action: str) -> None:
        """Bridge voice actions that control the pipeline lifecycle."""
        if action == "resume" and self.pipeline.state.status == AppStatus.PAUSED:
            self.pipeline.resume()
            self._refresh_status()
        elif action == "pause" and self.pipeline.state.status == AppStatus.RUNNING:
            self.pipeline.pause()
            self._refresh_status()

    def _on_voice_toggle(self) -> None:
        if not self.voice.available:
            QMessageBox.information(
                self, "Voice control",
                "The 'vosk' speech-recognition package is not installed.\n\n"
                "Install it with:\n    pip install vosk pyaudio\nto enable voice commands.",
            )
            return
        if self.voice.running:
            self.voice.stop()
            self._voice_button.setText("START VOICE")
            self._voice_status.setText("Stopped")
            self._voice_status.setStyleSheet(f"color:{DARK_WARNING}; font-weight:600;")
        elif self.voice.start():
            self._voice_button.setText("STOP VOICE")
            self._voice_status.setText("Listening...")
            self._voice_status.setStyleSheet(f"color:{DARK_SUCCESS}; font-weight:600;")

    def _on_voice_language_change(self, index: int) -> None:
        code = ["en", "fr", "ar"][index]
        self.settings.set("language", code)
        self.voice.language = code

    def _on_auto_start_toggle(self, checked: bool) -> None:
        from app.privacy.tray import set_auto_start  # noqa: PLC0415
        self.settings.set("auto_start", checked)
        ok = set_auto_start(checked)
        if not ok:
            _LOG.warning("Could not update auto-start registry entry")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_hand_detected(self, event: Event) -> None:
        hand = event.data.get("hand")
        if hand is not None:
            self._last_hand = hand

    def _on_hand_lost(self, event: Event) -> None:
        self._last_hand = None

    def _on_gesture_detected(self, event: Event) -> None:
        gesture = event.data.get("gesture")
        if gesture is not None:
            self._last_gesture_event_ts = time.monotonic()
            name = gesture.name.name.replace("_", " ").title()
            self._status_gesture.update("good", f"{name} ✓")

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        st = self.pipeline.state
        ts = self.pipeline.telemetry
        st.update(fps=ts.fps, latency_ms=ts.latency_ms)

        self._update_camera_preview()
        self._update_control_buttons(st.status)

        cam_status = "Connected" if st.camera_active else "Disconnected"
        track_status = "Active" if st.tracking_active else "Inactive"
        touch_mode = "Active" if st.mode.value == "virtual_touch" else "Air Mouse"
        quality = st.stats.tracking_quality

        self._status_camera.update(
            "good" if st.camera_active else "inactive", cam_status)
        self._status_tracking.update(
            "good" if st.tracking_active else "inactive", track_status)
        self._status_touch.update(
            "good" if st.mode.value == "virtual_touch" else "warning", touch_mode)
        self._status_fps.update(
            "good" if ts.fps >= 25 else ("warning" if ts.fps >= 15 else "poor"),
            f"{ts.fps:.0f}" if ts.fps > 0 else "--")
        self._status_latency.update(
            "good" if ts.latency_ms < 50 else ("warning" if ts.latency_ms < 100 else "poor"),
            f"{ts.latency_ms:.0f} ms" if ts.latency_ms > 0 else "--")
        self._status_quality.update(
            quality.lower() if quality else "inactive", quality or "--")
        self._status_gesture.update(
            "good" if st.stats.gesture else "inactive",
            st.stats.gesture or "None")

    def _update_control_buttons(self, status: AppStatus) -> None:
        """Reflect pipeline status on the control buttons.

        Without this, START stays enabled (and looks clickable) even while
        the pipeline is already running, so clicking it again appears to do
        nothing - confusing users into thinking the button is broken.
        """
        active = self.pipeline.is_running
        self._btn_start.setEnabled(not active)
        self._btn_pause.setEnabled(active)
        self._btn_pause.setText("RESUME" if status == AppStatus.PAUSED else "PAUSE")

    def _update_camera_preview(self) -> None:
        """Render the latest camera frame (with overlays) into the preview label."""
        frame = self.camera.grab()
        if frame is None:
            if self.camera.is_simulation:
                self._cam_preview_label.setText("Simulation mode – no real camera available")
            return
        try:
            import cv2  # noqa: PLC0415
            import numpy as np
            from PySide6.QtGui import QImage, QPixmap  # noqa: PLC0415
            from app.tracking.models import SKELETON_CONNECTIONS  # noqa: PLC0415

            # Work on a copy: the live frame is shared with the capture thread.
            canvas = frame.copy()
            h, w = canvas.shape[:2]

            # Hand skeleton overlay
            hand = self._last_hand
            if hand is not None and hand.landmarks:
                pts = {i: (int(lm.x * w), int(lm.y * h))
                       for i, lm in enumerate(hand.landmarks)}
                for a, b in SKELETON_CONNECTIONS:
                    if a in pts and b in pts:
                        cv2.line(canvas, pts[a], pts[b], (0, 255, 120), 2)
                for idx, color in [(4, (0, 0, 255)), (8, (255, 0, 0))]:
                    if idx in pts:
                        cv2.circle(canvas, pts[idx], 6, color, -1)

            # Calibration guide overlay
            if self.pipeline.state.status == AppStatus.CALIBRATING:
                for pt in self.calibrator.recorded_points:
                    cv2.circle(canvas, (int(pt[0] * w), int(pt[1] * h)), 12,
                               (255, 165, 0), -1)
                if hand is not None and hand.index_finger_tip is not None:
                    tip = hand.index_finger_tip
                    cv2.circle(canvas, (int(tip[0] * w), int(tip[1] * h)), 8,
                               (0, 255, 255), -1)
                corner = self.calibrator.get_current_corner()[0].replace("_", " ").title()
                cv2.putText(canvas, f"Point at {corner}", (16, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)

            rgb = np.ascontiguousarray(canvas[:, :, ::-1])  # BGR -> RGB
            img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            self._cam_preview_label.setPixmap(
                QPixmap.fromImage(img).scaled(
                    min(w, 620), min(h, 380),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        self.keyboard_overlay.hide()
        self._on_exit()
        event.accept()