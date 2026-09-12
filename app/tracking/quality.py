"""Tracking quality scoring based on landmark confidence and visibility."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

from app.tracking.models import HandData


class QualityLevel(enum.Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    POOR = "poor"


@dataclass
class QualityReport:
    level: QualityLevel
    score: float  # 0..1
    lighting_ok: bool = True
    hand_visible: bool = True
    confidence_ok: bool = True
    recommendations: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.recommendations is None:
            self.recommendations = []


class TrackingQualityMonitor:
    """Compute a real-time quality score for hand tracking."""

    def __init__(self, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence

    def evaluate(self, hand: Optional[HandData]) -> QualityReport:
        if hand is None:
            return QualityReport(
                level=QualityLevel.POOR,
                score=0.0,
                hand_visible=False,
                recommendations=["Show your hand to the camera.", "Improve lighting."],
            )

        score = 1.0
        recs: list[str] = []

        # Confidence
        conf = hand.confidence
        if conf < self.min_confidence:
            score *= 0.5
            recs.append(f"Low confidence ({conf:.0%}). Improve lighting or hand position.")

        # Landmark count
        visible = sum(1 for lm in hand.landmarks if lm.visibility > 0.5)
        if visible < 15:
            score *= 0.6
            recs.append(f"Only {visible}/21 landmarks visible. Keep entire hand in frame.")

        # All fingertips visible?
        from app.tracking.models import INDEX_TIP, THUMB_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP
        tips = [INDEX_TIP, THUMB_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
        tips_visible = sum(1 for t in tips if t < len(hand.landmarks) and hand.landmarks[t].visibility > 0.5)
        if tips_visible < 3:
            score *= 0.7
            recs.append("Some fingertips are not visible. Adjust hand distance.")

        # Clamp
        score = max(0.0, min(1.0, score))

        if score >= 0.85:
            level = QualityLevel.EXCELLENT
        elif score >= 0.65:
            level = QualityLevel.GOOD
        elif score >= 0.4:
            level = QualityLevel.WARNING
        else:
            level = QualityLevel.POOR
            recs.append("Tracking quality is poor. Check camera and lighting.")

        return QualityReport(
            level=level,
            score=score,
            confidence_ok=conf >= self.min_confidence,
            hand_visible=True,
            recommendations=recs,
        )