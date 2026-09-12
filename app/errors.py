"""Application error hierarchy."""
from __future__ import annotations


class HadjError(Exception):
    """Base exception for HADJ AIR TOUCH."""

class TrackingError(HadjError):
    """Hand tracking failed or lost."""

class CalibrationError(HadjError):
    """Calibration problem."""

class CameraError(HadjError):
    """Camera unavailable or unusable."""

class InputError(HadjError):
    """Windows input injection failed."""