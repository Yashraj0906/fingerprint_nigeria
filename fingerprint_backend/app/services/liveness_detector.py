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


# ── Thresholds ────────────────────────────────────────────────────────────────
_GLARE_RATIO_MAX   = 0.12   # >12% saturated-white pixels → screen replay
_LBP_VAR_MIN       = 18.0   # real skin local texture variance floor
_SKIN_RATIO_MIN    = 0.15   # at least 15% of crop must be skin-tone pixels
_MOIRE_SCORE_MAX   = 0.55   # DFT periodicity above this → screen/print artifact


def evaluate(gray: np.ndarray, hand: HandDetectionResult,
             bgr: Optional[np.ndarray] = None) -> LivenessResult:
    """
    4-layer contactless liveness check.

    Layer 1 — MediaPipe hand presence (primary hard gate)
    Layer 2 — Screen-replay glare guard (saturation check, tightened to 12%)
    Layer 3 — LBP texture variance (real skin has characteristic local texture)
    Layer 4 — Skin colour detection in HSV (real finger falls in skin-tone range)

    Layers 1 & 2 are hard gates (fail → reject immediately).
    Layers 3 & 4 are soft scoring signals that reduce confidence.
    The final confidence combines all four layers.
    """

    # ── Layer 1: MediaPipe hard gate ──────────────────────────────────────────
    if not hand.detected:
        return LivenessResult(
            passed=False,
            reason="No hand detected — place your finger in the frame",
            confidence=0.95
        )

    # ── Layer 2: Screen-replay glare guard ────────────────────────────────────
    _, bright_mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    glare_ratio    = cv2.countNonZero(bright_mask) / float(gray.shape[0] * gray.shape[1])

    if glare_ratio > _GLARE_RATIO_MAX:
        return LivenessResult(
            passed=False,
            reason="Screen replay or excessive glare detected",
            confidence=0.85
        )

    # ── Layer 3: LBP texture variance ─────────────────────────────────────────
    # Real skin has highly varied local micro-texture (ridges, pores, wrinkles).
    # A printed photo or screen is texturally uniform at the local level.
    #
    # We use a fast approximation: compute per-pixel local standard deviation
    # over a 5×5 neighbourhood, then take the mean. Real skin gives ~20-60,
    # flat prints/screens give ~5-15.
    lbp_var = _local_texture_variance(gray)
    lbp_ok  = lbp_var >= _LBP_VAR_MIN

    # ── Layer 4: Skin colour detection ────────────────────────────────────────
    # Real skin falls within a specific HSV range regardless of lighting.
    # Screens and printed paper do not (or only marginally) match this range.
    skin_ratio = _skin_colour_ratio(bgr if bgr is not None else _gray_to_bgr(gray))
    skin_ok    = skin_ratio >= _SKIN_RATIO_MIN

    # ── Confidence aggregation ────────────────────────────────────────────────
    # Start from MediaPipe confidence, apply soft penalties for failed layers.
    confidence = hand.confidence
    confidence *= (1.0 - 0.08 * (glare_ratio / _GLARE_RATIO_MAX))  # glare penalty

    if not lbp_ok:
        # Low texture → reduce confidence, but don't hard-fail (lighting can affect this)
        confidence *= 0.75

    if not skin_ok:
        # Non-skin colour → reduce confidence
        confidence *= 0.80

    confidence = float(np.clip(confidence, 0.0, 1.0))

    # Hard fail only if BOTH soft layers fail (belt-and-suspenders)
    if not lbp_ok and not skin_ok:
        return LivenessResult(
            passed=False,
            reason="Spoof detected — low texture and no skin tone",
            confidence=confidence
        )

    return LivenessResult(passed=True, reason=None, confidence=confidence)


# ── Layer 3 helper: local texture variance (LBP proxy) ───────────────────────

def _local_texture_variance(gray: np.ndarray) -> float:
    """
    Fast LBP-proxy: mean of per-pixel local standard deviation in a 5×5 window.

    Computes local variance using the identity:
        local_var = E[x²] - E[x]²
    via box filtering (O(N) regardless of window size).

    Real skin texture: mean local std ≈ 20–60
    Printed / screen:  mean local std ≈ 3–15
    """
    f   = gray.astype(np.float32)
    k   = (5, 5)
    mu  = cv2.blur(f, k)
    mu2 = cv2.blur(f * f, k)
    var = np.clip(mu2 - mu * mu, 0, None)
    return float(np.mean(np.sqrt(var)))


# ── Layer 4 helper: skin colour ratio ────────────────────────────────────────

def _skin_colour_ratio(bgr: np.ndarray) -> float:
    """
    Fraction of pixels that fall within the skin-tone HSV range.

    HSV skin-tone envelope (covers light through dark skin tones):
      H: 0–25  (red-orange hue, wraps at 180 in OpenCV)
      S: 20–170 (not too grey, not fully saturated)
      V: 50–255 (not too dark)

    Also includes the upper hue wrap-around (H: 165–180) for very
    reddish skin tones near the red boundary.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Primary skin range
    mask1 = cv2.inRange(hsv,
                        np.array([0,  20,  50], dtype=np.uint8),
                        np.array([25, 170, 255], dtype=np.uint8))
    # Upper wrap (reddish tones)
    mask2 = cv2.inRange(hsv,
                        np.array([165, 20,  50], dtype=np.uint8),
                        np.array([180, 170, 255], dtype=np.uint8))

    skin_pixels = cv2.countNonZero(cv2.bitwise_or(mask1, mask2))
    total       = bgr.shape[0] * bgr.shape[1]
    return float(skin_pixels / total)


def _gray_to_bgr(gray: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
