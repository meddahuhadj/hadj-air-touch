# HADJ AIR TOUCH

**AI-powered virtual touchscreen system for Windows 11.**

> HADJ AIR TOUCH allows you to interact with a normal (non-touch) Windows
> computer using only your hands and a webcam — **no touchscreen, no touch frame,
> no external hardware.**

---

## Features

- **Air Mouse**: Index finger controls the Windows cursor
- **Virtual Touch**: Finger reaching a virtual plane triggers touch actions
- **Gesture Engine**: Pinch-to-click, double-pinch, right-click, swipe, zoom, grab,
  thumbs-up (volume), wave (pause/resume)
- **Screen Calibration**: 4-point homography with quality score
- **Multi-Monitor**: Detect and target any connected display
- **Windows Integration**: Native mouse/keyboard via `SendInput` (ctypes),
  incl. app shortcuts (undo/redo, save, copy/paste, tabs, minimize/maximize,
  lock screen, screenshot)
- **On-Screen Keyboard**: QWERTY, AZERTY, Arabic, Emoji layouts
- **Voice Control**: Offline via Vosk (optional)
- **HADJ AI Assistant**: Built-in tips and troubleshooting
- **Profiles**: Auto-switching per application (browser, presentation, media,
  CAD, office, developer)
- **Privacy-First**: All processing local; no cloud upload
- **Accessibility Mode**: Larger cursor, slower movement, high contrast
- **Emergency Stop**: `Ctrl+Alt+H` instantly pauses all interaction

---

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+
- Webcam (720p+ recommended, 30 FPS+)
- Good lighting on your hands

## Installation

```bash
# Clone or extract the project
cd "HADJ AIR TOUCH  2"

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
python -m pip install -r requirements.txt
```

### Offline / restricted networks

If this PC blocks `pip` (Application Control policy) or has no internet, prepare
the wheels on a connected machine with the **same Python version and
architecture**, then copy them over:

```bash
# On a connected machine (match the target: e.g. Python 3.13, win_amd64)
python -m pip download -r requirements.txt -d wheels
```

```powershell
# On the offline PC
python -m pip install --no-index --find-links wheels -r requirements.txt
```

The application also **runs without any third-party package** for verification:
`python main.py --self-test` works on a clean Python install and every module
import degrades gracefully (tracking/camera/GUI features report as
unavailable instead of crashing).

## Running

### Desktop Application (PySide6 / Windows API)

```bash
python main.py
```

### Progressive Web App (PWA) - Any Browser / Offline

HADJ AIR TOUCH can also run directly in any web browser (Chrome, Edge, Safari, Firefox, Mobile/Tablet):

```bash
python run_pwa.py
```

This launches a local web server at `http://localhost:8080` and opens your browser. You can click **"Install App"** in the browser to install HADJ AIR TOUCH as a standalone desktop/mobile app that works 100% offline!

A hosted copy of the PWA is deployed at [https://hadj-air-touch-pwa.vercel.app](https://hadj-air-touch-pwa.vercel.app). The web version supports the same core gestures (pointer, pinch click, double pinch, grab/drag, swipe) plus **Thumbs Up 👍** (feedback) and **Wave 👋** (pause/resume tracking).

### Headless / Self-test mode

```bash
# Run built-in tests (no GUI, no camera needed)
python main.py --self-test
```

### System diagnostics

```bash
# Print which components are present/missing (useful on restricted PCs)
python main.py --doctor
```

## Usage

1. **Launch** the application
2. Click **START** to begin tracking
3. **Point** your index finger to move the cursor
4. **Pinch** (thumb + index finger together) to click
5. Run **Calibration** from the sidebar for Virtual Touch mode
6. Choose **Profiles** from the sidebar to optimise for different apps
7. Press **Ctrl+Alt+H** at any time to emergency stop

---

## Architecture

```
app/
├── main.py                # Entry point (delegates to GUI or CLI)
├── cli.py                 # Headless / self-test runner
├── gui.py                 # Qt GUI bootstrap
├── config.py              # Settings (JSON persistence)
├── logging_conf.py        # Logging setup
├── errors.py              # Exception hierarchy
├── version.py             # Version & metadata
├── core/
│   ├── controller.py      # Pipeline orchestrator
│   ├── state.py           # Shared mutable app state
│   └── events.py          # Pub-sub event bus
├── camera/
│   ├── manager.py         # Camera enumeration
│   └── capture.py         # Threaded capture + simulation
├── tracking/
│   ├── models.py          # 21-point hand landmark dataclasses
│   ├── hand_tracker.py    # MediaPipe wrapper
│   └── quality.py         # Real-time tracking quality scoring
├── gestures/
│   ├── engine.py          # Gesture recognition engine
│   ├── gestures.py        # Individual gesture detectors
│   └── mapping.py         # Gesture → action mapping (profile-aware)
├── calibration/
│   ├── homography.py      # DLT homography (pure Python + numpy)
│   └── calibrator.py      # 4-point guided workflow
├── virtual_touch/
│   ├── engine.py          # Touch state machine (IDLE → POINTING → …)
│   ├── plane.py           # Virtual screen plane model
│   └── smoothing.py       # EMA + One Euro filter
├── windows_input/
│   ├── dispatcher.py       # Event → mouse/keyboard action bridge
│   ├── mouse.py            # SendInput mouse control
│   ├── keyboard.py         # SendInput keyboard control
│   ├── screen.py           # Monitor enumeration
│   └── _win32_enums.py     # Low-level Win32 ctypes
├── profiles/
│   └── manager.py          # Per-app gesture profiles
├── privacy/
│   ├── guard.py            # Camera indicator, emergency stop
│   └── tray.py             # System tray + auto-start
├── assistant/
│   └── hadj_ai.py          # Rule-based assistant tips
├── voice/
│   └── controller.py       # Local voice recognition (Vosk)
├── keyboard/
│   └── virtual_keyboard.py # On-screen keyboard layouts
├── services/
│   └── telemetry.py        # FPS / latency tracking
├── utils/
│   └── vectors.py          # 2D/3D vector math
└── ui/
    ├── main_window.py      # Main dashboard window
    ├── theme.py            # Windows 11 dark/light theme
    ├── widgets.py          # Reusable UI components
    └── pages/              # (integrated in main_window)
```

## Key Design Principles

1. **Offline-First**: Core interaction works without internet
2. **Privacy**: Camera data never leaves the computer
3. **Modularity**: Each subsystem is independent and testable
4. **Graceful Degradation**: Missing optional deps → clear error, not crash
5. **Low Latency**: 30+ FPS target with smoothed cursor movement
6. **Accessibility**: Works for users with limited mobility

## Building a Windows Executable

```bash
python -m pip install pyinstaller
pyinstaller --name "HADJ Air Touch" --onefile --windowed --icon=app.ico main.py
```

## Testing

227 unit/integration tests cover homography, gesture detection (incl. swipe,
thumbs-up and wave), double-pinch, virtual-touch state machine, smoothing,
config persistence, input dispatch, profiles, HADJ AI, tracking quality,
virtual keyboard, voice command mapping, event bus, app state, camera/screen
managers, the full gesture→dispatcher chain, pipeline controller orchestration,
the guided calibration workflow, the mediapipe hand-tracker wrapper (both
installed and degraded paths), and the system-diagnostics report (via mocks,
no camera/hardware needed).

```bash
python main.py --self-test
```

Or run the unit tests directly:

```bash
python -m unittest discover -s app/tests -p "test_*.py" -v
```

## Configuration

Settings are stored at:
```
%APPDATA%/HADJAirTouch/settings.json
```

You can edit this file directly or use the Settings page in the application.

## Limitations

> **HADJ AIR TOUCH provides VIRTUAL TOUCH / CAMERA-BASED INTERACTION, NOT physical touch detection.**

Accuracy depends on:
- Camera quality and frame rate
- Room lighting
- Camera position and angle
- Distance from camera to hand
- Hand visibility and background contrast
- Tracking model confidence

## License

MIT License – See LICENSE file.

---

*HADJ AIR TOUCH – An AI-powered virtual touchscreen system that allows users to
interact with a normal Windows computer using their hands and webcam — without a
touchscreen, without a touch frame, and without external touch hardware.*
