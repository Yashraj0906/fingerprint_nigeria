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
    Thresholds: >70 ACCEPT | 40-70 RETRY | <40 REJECT
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

    # Compute raw coverage ratio for guidance (different from score)
    _, binary_raw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    raw_coverage_ratio = cv2.countNonZero(binary_raw) / (gray.shape[0] * gray.shape[1])

    guidance = _guidance_message(blur, contrast, ridges, coverage, float(gray.mean()), raw_coverage_ratio)

    return QualityResult(composite, blur, contrast, ridges, coverage, verdict, guidance)


# ── Guidance ──────────────────────────────────────────────────────────────────

def _guidance_message(blur: float, contrast: float, ridge: float,
                      coverage: float, brightness: float,
                      raw_coverage_ratio: float = 0.5) -> Optional[str]:
    """Single most-important actionable hint. Priority: lighting > blur > position > ridges."""
    if brightness < 55:
        return "Too dark — move to better lighting"
    if brightness > 215:
        return "Too bright — reduce glare or reflections"
    if blur < 35:
        return "Hold still — finger is blurry"
    if raw_coverage_ratio < 0.20:
        return "Move closer — finger too small in frame"
    if raw_coverage_ratio > 0.90:
        return "Move hand back — too close to camera"
    if contrast < 30:
        return "Improve lighting — low contrast"
    if ridge < 30:
        return "Flatten finger slightly — ridges unclear"
    return None


# ── BLR: Blur score ───────────────────────────────────────────────────────────

def _blur_score(gray: np.ndarray) -> float:
    """
    Combined Laplacian variance + Tenengrad (Sobel gradient energy).

    WHY TWO MEASURES:
    - Laplacian variance: fast, good for uniform blur (defocus, motion)
      but amplifies noise on high-ISO camera feeds.
    - Tenengrad: sum of squared Sobel gradients — far less sensitive to
      pixel noise because it squares the response (noise averages near 0,
      true edges stay large). Better on low-light / compressed video.

    NORMALIZATION:
    - Laplacian: finger crop variance typically 50–500 → divide by 5
    - Tenengrad: mean gradient energy on a sharp crop ~100–800 → divide by 8
    - Both clipped to [0, 100] and averaged equally.
    """
    # Laplacian variance
    lap          = cv2.Laplacian(gray, cv2.CV_64F)
    lap_score    = float(np.clip(lap.var() / 5.0, 0.0, 100.0))

    # Tenengrad (Sobel gradient energy)
    sx           = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sy           = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad    = float(np.mean(sx ** 2 + sy ** 2))
    tenengrad_score = float(np.clip(tenengrad / 8.0, 0.0, 100.0))

    return float(np.clip(0.5 * lap_score + 0.5 * tenengrad_score, 0.0, 100.0))


# ── ILLUM: Illumination / contrast score ──────────────────────────────────────

def _contrast_score(gray: np.ndarray) -> float:
    """
    Three-part illumination score:

    1. RMS contrast (std of pixel intensities)
       Good lighting → well-spread histogram → high std.

    2. Histogram entropy
       A well-exposed finger uses most of the 0-255 range evenly → high
       Shannon entropy.  Flat / blown-out / fully-dark images have low entropy.
       Max possible entropy for 8-bit image = 8 bits.

    3. Local uniformity
       Split crop into 4 quadrants, measure std of their mean brightnesses.
       Low std = even lighting across finger. High std = shadow on one side
       or specular hotspot.

    4. Brightness penalty (same as before — applied to RMS score only)
       Optimal 80-180; harshly penalises <50 or >210.

    WEIGHTS: 50% RMS×brightness + 30% entropy + 20% uniformity
    """
    mean_b = float(gray.mean())
    stddev = float(gray.std())

    # Part 1 — RMS contrast with brightness penalty
    base_rms = float(np.clip(stddev / 0.64, 0.0, 100.0))
    if 80 <= mean_b <= 180:
        illum_factor = 1.0
    elif mean_b < 50 or mean_b > 210:
        illum_factor = 0.4
    elif mean_b < 80:
        illum_factor = 0.4 + 0.6 * (mean_b - 50) / 30.0
    else:
        illum_factor = 0.4 + 0.6 * (210 - mean_b) / 30.0
    rms_score = float(np.clip(base_rms * illum_factor, 0.0, 100.0))

    # Part 2 — Histogram entropy
    hist      = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist_norm = hist / (hist.sum() + 1e-9)
    nonzero   = hist_norm[hist_norm > 0]
    entropy   = float(-np.sum(nonzero * np.log2(nonzero)))   # 0–8 bits
    entropy_score = float(np.clip(entropy / 7.5 * 100.0, 0.0, 100.0))

    # Part 3 — Local uniformity (4-quadrant mean spread)
    h, w = gray.shape
    qh, qw = max(h // 2, 1), max(w // 2, 1)
    quadrants = [
        gray[:qh, :qw], gray[:qh, qw:],
        gray[qh:, :qw], gray[qh:, qw:],
    ]
    q_means = [float(q.mean()) for q in quadrants if q.size > 0]
    spread  = float(np.std(q_means)) if len(q_means) > 1 else 0.0
    # spread < 15 → excellent uniformity, spread > 60 → bad shadow/glare
    uniformity_score = float(np.clip(100.0 - spread / 0.60, 0.0, 100.0))

    return float(np.clip(
        0.50 * rms_score + 0.30 * entropy_score + 0.20 * uniformity_score,
        0.0, 100.0
    ))


# ── Ridge clarity score (unchanged) ──────────────────────────────────────────

def _ridge_clarity_score(gray: np.ndarray) -> float:
    """Canny edge density. Ideal fingerprint ~10-20% edge pixels → score 100."""
    edges       = cv2.Canny(gray, 40, 120)
    edge_pixels = cv2.countNonZero(edges)
    total       = gray.shape[0] * gray.shape[1]
    ratio       = edge_pixels / total
    normalised  = 1.0 - abs(ratio - 0.15) / 0.15
    return float(np.clip(normalised * 100.0, 0.0, 100.0))


# ── Coverage score (unchanged) ────────────────────────────────────────────────

def _coverage_score(gray: np.ndarray) -> float:
    """Otsu coverage — ideal finger covers 30-80% of ROI."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    non_zero  = cv2.countNonZero(binary)
    total     = gray.shape[0] * gray.shape[1]
    ratio     = non_zero / total

    if ratio < 0.30:
        return float(np.clip(ratio / 0.30 * 100.0, 0.0, 100.0))
    elif ratio > 0.80:
        return float(np.clip((1.0 - ratio) / 0.20 * 100.0, 0.0, 100.0))
    return 100.0
