import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional
from app.services.hand_detector import HandDetectionResult


@dataclass
class LivenessResult:
    passed:     bool
    reason:     Optional[str]
    confidence: float   # 0.0 – 1.0


# Secondary guard: if >15% of pixels are saturated bright (>245), assume screen replay
_SCREEN_GLARE_RATIO_MAX = 0.15


def evaluate(gray: np.ndarray, hand: HandDetectionResult) -> LivenessResult:
    """
    Contactless liveness check (webcam / phone camera).

    Layer 1 — MediaPipe hand detection (primary signal)
      → If MediaPipe detected a real hand in the frame, the finger is live.
        A printed photo or flat spoof will rarely produce valid 21-point hand
        landmarks under natural shooting conditions.

    Layer 2 — Screen-replay guard (secondary, soft)
      → Excessive saturated-bright pixels indicate a phone/monitor being
        held up instead of a real finger.
    """

    # Layer 1: hand presence = live finger
    if not hand.detected:
        return LivenessResult(
            passed=False,
            reason="No hand detected — place your finger in the frame",
            confidence=0.95
        )

    # Layer 2: screen glare check
    _, bright_mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    glare_ratio = cv2.countNonZero(bright_mask) / float(gray.shape[0] * gray.shape[1])

    if glare_ratio > _SCREEN_GLARE_RATIO_MAX:
        return LivenessResult(
            passed=False,
            reason="Screen replay or excessive glare detected",
            confidence=0.80
        )

    # Passed — confidence inherits from MediaPipe + small glare bonus
    glare_penalty = glare_ratio / _SCREEN_GLARE_RATIO_MAX  # 0.0 – 1.0
    confidence = float(np.clip(hand.confidence * (1.0 - 0.1 * glare_penalty), 0.0, 1.0))

    return LivenessResult(passed=True, reason=None, confidence=confidence)
