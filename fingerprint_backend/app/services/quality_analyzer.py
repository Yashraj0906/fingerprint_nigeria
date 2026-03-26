import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    RETRY  = "RETRY"
    REJECT = "REJECT"


@dataclass
class QualityResult:
    score:           float
    blur_score:      float
    contrast_score:  float
    ridge_score:     float
    coverage_score:  float
    verdict:         Verdict
    guidance_message: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.ACCEPT


def analyze(gray: np.ndarray) -> QualityResult:
    """
    Four-metric quality scorer for contactless fingerprint capture.
    Weights: blur=0.30, contrast=0.20, ridges=0.30, coverage=0.20

    Thresholds:
      > 70  → ACCEPT
      40-70 → RETRY
      < 40  → REJECT

    Also returns a human-readable guidance_message for the live UI.
    """
    blur     = _blur_score(gray)
    contrast = _contrast_score(gray)
    ridges   = _ridge_clarity_score(gray)
    coverage = _coverage_score(gray)

    composite = float(np.clip(
        blur * 0.30 + contrast * 0.20 + ridges * 0.30 + coverage * 0.20,
        0.0, 100.0
    ))

    if composite > 70:
        verdict = Verdict.ACCEPT
    elif composite >= 40:
        verdict = Verdict.RETRY
    else:
        verdict = Verdict.REJECT

    guidance = _guidance_message(blur, contrast, ridges, coverage,
                                 float(gray.mean()))

    return QualityResult(composite, blur, contrast, ridges, coverage,
                         verdict, guidance)


# ── Guidance ──────────────────────────────────────────────────────────────────

def _guidance_message(blur: float, contrast: float, ridge: float,
                      coverage: float, brightness: float) -> Optional[str]:
    """
    Returns the single most important actionable hint for the user.
    Priority: lighting > blur > position > contrast > ridges
    """
    if brightness < 55:
        return "Too dark — move to better lighting"
    if brightness > 215:
        return "Too bright — reduce glare or reflections"
    if blur < 40:
        return "Hold still — finger is blurry"
    if coverage < 30:
        return "Move closer — finger too small in frame"
    if coverage > 95:
        return "Move hand back — too close to camera"
    if contrast < 35:
        return "Improve lighting — low contrast"
    if ridge < 35:
        return "Flatten finger slightly — ridges unclear"
    return None


# ── Individual metrics ────────────────────────────────────────────────────────

def _blur_score(gray: np.ndarray) -> float:
    """
    Laplacian variance — higher = sharper.
    Normalised: variance~500 → score 100.
    Track A reference: BLUR_THRESHOLD_OPTIMAL = 100 (on full frame).
    On a cropped finger region variance is typically 50-300, so /5.0 is appropriate.
    """
    lap      = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(lap.var())
    return float(np.clip(variance / 5.0, 0.0, 100.0))


def _contrast_score(gray: np.ndarray) -> float:
    """
    RMS contrast (std of pixel intensities). stddev~64 → score 100.
    Also applies a brightness penalty (Track A illumination check):
    optimal brightness 80-180, penalised below 50 or above 210.
    """
    stddev     = float(gray.std())
    mean_b     = float(gray.mean())
    base_score = float(np.clip(stddev / 0.64, 0.0, 100.0))

    # Illumination penalty from Track A reference thresholds
    if 80 <= mean_b <= 180:
        illum_factor = 1.0
    elif mean_b < 50 or mean_b > 210:
        illum_factor = 0.4
    else:
        # Linear ramp between dim/bright boundaries
        if mean_b < 80:
            illum_factor = 0.4 + 0.6 * (mean_b - 50) / 30.0
        else:
            illum_factor = 0.4 + 0.6 * (210 - mean_b) / 30.0

    return float(np.clip(base_score * illum_factor, 0.0, 100.0))


def _ridge_clarity_score(gray: np.ndarray) -> float:
    """Canny edge density. Ideal fingerprint ~10-20% edge pixels → score 100."""
    edges       = cv2.Canny(gray, 40, 120)
    edge_pixels = cv2.countNonZero(edges)
    total       = gray.shape[0] * gray.shape[1]
    ratio       = edge_pixels / total
    normalised  = 1.0 - abs(ratio - 0.15) / 0.15
    return float(np.clip(normalised * 100.0, 0.0, 100.0))


def _coverage_score(gray: np.ndarray) -> float:
    """
    Otsu coverage — ideal finger covers 30-80% of ROI.
    Track A reference: optimal coverage 15-35% of full frame.
    On a pre-cropped finger image the ratio should be higher, so 30-80% is appropriate.
    """
    _, binary  = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    non_zero   = cv2.countNonZero(binary)
    total      = gray.shape[0] * gray.shape[1]
    ratio      = non_zero / total

    if ratio < 0.30:
        return float(np.clip(ratio / 0.30 * 100.0, 0.0, 100.0))
    elif ratio > 0.80:
        return float(np.clip((1.0 - ratio) / 0.20 * 100.0, 0.0, 100.0))
    return 100.0
