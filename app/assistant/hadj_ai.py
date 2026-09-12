"""HADJ AI – built-in rule-based assistant for guidance and troubleshooting."""
from __future__ import annotations

import logging
from typing import Optional

_LOG = logging.getLogger(__name__)

_TIPS: dict[str, str] = {
    "calibration_start": (
        "Calibration Mode\n\n"
        "You will see four corners on screen. Point your index finger at each one "
        "and hold steady for about 1 second.\n\n"
        "Tip: Sit at your normal distance (40–70 cm from the camera)."
    ),
    "calibration_done": (
        "Calibration complete!\n\n"
        "Quality score: {quality:.0%}\n\n"
        "You can recalibrate anytime from Settings."
    ),
    "tracking_lost": (
        "Hand tracking lost.\n\n"
        "Possible causes:\n"
        "• Your hand left the camera view\n"
        "• Lighting is too dim\n"
        "• Background is too similar to skin colour\n\n"
        "Try: Improve lighting or keep your hand centred in view."
    ),
    "low_confidence": (
        "Tracking confidence is low ({confidence:.0%}).\n\n"
        "Recommendations:\n"
        "• Improve room lighting\n"
        "• Avoid backlighting (window behind you)\n"
        "• Keep your hand 40–70 cm from the camera"
    ),
    "too_close": (
        "Your hand appears too close to the camera.\n"
        "Move it approximately 40–70 cm away."
    ),
    "too_far": (
        "Your hand appears too far from the camera.\n"
        "Move closer or ensure the camera can see your hand clearly."
    ),
    "gesture_pinch": (
        "Pinch gesture: Bring your thumb and index finger tips together.\n"
        "This triggers a left click."
    ),
    "gesture_point": (
        "Point gesture: Extend your index finger while folding the others.\n"
        "This controls the mouse cursor."
    ),
    "gesture_right_click": (
        "Right-click gesture: Touch your thumb to your middle finger.\n"
        "This triggers a right click."
    ),
    "gesture_open_palm": (
        "Open palm: Spread all five fingers.\n"
        "This pauses the interaction."
    ),
    "emergency_stop": (
        "Emergency Stop\n\n"
        "Press Ctrl+Alt+H at any time to immediately pause all interaction.\n"
        "The camera and tracking will stop until you press Resume."
    ),
    "camera_position": (
        "Camera Positioning Tips:\n\n"
        "• Place the camera above or below your monitor\n"
        "• Face the camera toward your working area\n"
        "• Ensure even lighting on your hands\n"
        "• Avoid strong backlight (window behind you)\n"
        "• 720p minimum resolution recommended\n"
        "• 30 FPS or higher recommended"
    ),
    "lighting": (
        "Lighting Tips:\n\n"
        "• Use soft, even lighting\n"
        "• Avoid harsh overhead shadows\n"
        "• A desk lamp facing your hands helps\n"
        "• Avoid direct sunlight on the camera lens\n"
        "• The camera's auto-exposure can help with minor variations"
    ),
    "sensitivity": (
        "Sensitivity:\n\n"
        "• Increase sensitivity if cursor moves too slowly\n"
        "• Decrease if cursor jumps or is jittery\n"
        "• Smoothing reduces jitter but adds slight lag\n"
        "• Start with defaults and adjust to your comfort"
    ),
}


class HadjAI:
    """Simple rule-based assistant that provides guidance."""

    def get_tip(self, topic: str, **format_kwargs: object) -> str:
        template = _TIPS.get(topic)
        if template is None:
            return f"I don't have a tip for '{topic}'. Try: calibration, gestures, lighting, sensitivity."
        try:
            return template.format(**format_kwargs)
        except (KeyError, IndexError):
            return template

    def diagnose(self, tracking_quality: str, confidence: float,
                 hand_visible: bool) -> str:
        """Provide a diagnosis based on current state."""
        if not hand_visible:
            return self.get_tip("tracking_lost")
        if confidence < 0.4:
            return self.get_tip("low_confidence", confidence=confidence)
        if tracking_quality == "POOR":
            return self.get_tip("low_confidence", confidence=confidence)
        if tracking_quality == "WARNING":
            return (
                "Tracking is functional but not optimal.\n"
                "Try the lighting tips or reposition your hand."
            )
        return "Everything looks good! Tracking quality is excellent."

    def list_topics(self) -> list[str]:
        return sorted(_TIPS.keys())