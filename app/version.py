# HADJ AIR TOUCH
# An AI-powered virtual touchscreen system for Windows 11.
#
# Features:
#   * Webcam + MediaPipe hand tracking (fully offline, local processing)
#   * 21-point hand landmark tracking
#   * Air mouse mode (index finger -> cursor)
#   * Virtual touch mode (finger reaching a virtual plane -> touch)
#   * Gesture engine (pinch, double pinch, right click, swipe, grab, ...)
#   * Screen calibration with homography + quality score
#   * Multi-monitor support
#   * Windows input via native APIs (ctypes/SendInput)
#   * Profiles, accessibility, voice control, HADJ AI assistant
#   * Privacy-first: camera data never leaves the computer
#
# Run:  python main.py
# Install: python -m pip install -r requirements.txt
#
# -----------------------------------------------------------------------------------
# VIRTUAL TOUCH / CAMERA-BASED INTERACTION
# HADJ AIR TOUCH does NOT convert your monitor into a physical touchscreen.
# It provides an AIR / VIRTUAL touch interface driven by a webcam.
# Accuracy depends on camera quality, lighting, position, distance and stability.
# -----------------------------------------------------------------------------------

__version__ = "1.0.0"
APP_NAME = "HADJ AIR TOUCH"
APP_ID = "com.hadjairtouch.desktop"
ORGANIZATION = "HADJ"