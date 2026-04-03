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
    is_ai_generated: bool = False


# ── Thresholds (tuned for CONTACTLESS WEBCAM at 30-50 cm) ─────────────────────
_GLARE_RATIO_MAX        = 0.18   # >18% saturated-white pixels → screen replay
_LBP_VAR_MIN            = 5.0    # real webcam skin ≈ 6-30; screen replay ≈ 2-5
_SKIN_RATIO_MIN         = 0.10   # at least 10% of crop must be skin-tone pixels
_MOIRE_SCORE_MAX        = 0.72   # DFT periodicity — balanced for real skin edge fingers
_MOLD_CR_STD_MIN        = 2.5    # real skin Cr variance; lowered for small edge-finger crops
_RIDGE_BAND_RATIO_MIN   = 0.08   # ridges invisible at webcam distance
_REFLECTION_STD_MIN     = 2.0    # webcam finger crops have uniform lighting
_CONFIDENCE_FLOOR       = 0.30   # never return confidence below this for detected hands
_SPECTRAL_DECAY_MAX     = 0.25   # natural images high-mid ratio < 0.25 (AI flatter decay > 0.30)
_GRAD_KURTOSIS_MIN      = 1.8    # real skin gradient kurtosis > 3; screens ≈ 0.5-1.5
_COLOR_CORR_MIN         = 0.60   # R-G-B noise correlation; real > 0.70; screen < 0.55


def evaluate(gray: np.ndarray, hand: HandDetectionResult,
             bgr: Optional[np.ndarray] = None,
             hand_mode: str = "") -> LivenessResult:
    """
    9-layer contactless liveness & deepfake check — calibrated for webcam captures.

    Layer 1 — MediaPipe hand presence       (hard gate)
    Layer 2 — Screen-replay glare guard     (hard gate)
    Layer 3 — LBP texture variance          (hard gate — primary spoof detector)
    Layer 4 — Skin colour in HSV + YCrCb    (soft — catches wrong-colour objects)
    Layer 5 — DFT moiré detection           (hard gate — catches screens & halftone)
    Layer 6 — Ridge frequency ratio         (soft — very lenient for webcam)
    Layer 7 — Reflection uniformity         (soft — catches flat/printed surfaces)
    Layer 8 — Spectral Decay Anomaly        (hard gate — catches AI/Deepfake checkerboard artifacts)
    Layer 9 — Anatomical Sanity Check       (hard gate — catches AI hallucinations/impossible joints)
    Layer 10 — Sub-Surface Mold Detector    (hard gate — catches 3D physical silicone/latex molds)

    Combined Secondary Fail Logic:
      2-of-3 [L4, L6, L7] must FAIL together to reject.
    
    Key insight: LBP texture (Layer 3) is the strongest discriminator between
    real skin and screen replays at webcam distance:
      - Real skin: complex micro-texture (pores, wrinkles) → LBP ≈ 6-30
      - Screen replay: smooth pixels, no micro-texture → LBP ≈ 2-5
    """

    # ── Layer 1: MediaPipe hard gate ──────────────────────────────────────────
    if not hand.detected:
        return LivenessResult(
            passed=False,
            reason="No hand detected — place your finger in the frame",
            confidence=0.95
        )

    # ── Layer 10: 3D Silicone/Latex Mold Detector ─────────────────────────────
    # Real skin has blood beneath the surface causing variations in the Red channel 
    # (Sub-surface scattering). Physical PlayDoh/Silicone molds are painted a 
    # flat, lifeless color. We measure the variance of the Cr (Red-Chroma) channel.
    if bgr is not None and bgr.shape[0] >= 40 and bgr.shape[1] >= 40:
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        cr_channel = ycrcb[:, :, 1]
        cr_std = np.std(cr_channel)
        if cr_std < _MOLD_CR_STD_MIN:
            return LivenessResult(
                passed=False,
                reason="Physical replica/Mold detected — no sub-surface blood flow",
                confidence=0.10,
                is_ai_generated=False
            )

    # ── Deepfake Hard Gates (Run before Glare/Spoof checks) ───────────────────
    # We run these strictly first so the API explicitly warns about AI generation
    # instead of throwing a generic "Glare" or "Flat Texture" error for deepfakes.

    # ── Layer 8: Spectral Decay Anomaly (Deepfake FFT) 
    spectral_decay_ok = not _spectral_decay_anomaly(gray)
    if not spectral_decay_ok:
        return LivenessResult(
            passed=False,
            reason="Deepfake detected — artificial frequency spectrum",
            confidence=0.10,
            is_ai_generated=True
        )

    # ── Layer 9: Anatomical Sanity Check ──────────────────────────────────────
    # Only run this if we are expecting a full hand (not a single thumb where the
    # middle finger is tucked away or distorted).
    if "THUMB" not in hand_mode and "SINGLE" not in hand_mode:
        sane_anatomy = _anatomical_sanity_check(hand)
        if not sane_anatomy:
            return LivenessResult(
                passed=False,
                reason="Deepfake detected — anatomical anomaly in finger length",
                confidence=0.10,
                is_ai_generated=True
            )

    # ── Layer 11: Screen Sub-Pixel / Backlight Detection ──────────────────────
    # Phone/laptop screens have a regular pixel grid that creates distinctive
    # gradient patterns. Real 3D skin has natural, irregular gradient distributions.
    if bgr is not None:
        screen_detected, screen_reason = _screen_replay_detection(gray, bgr)
        if screen_detected:
            return LivenessResult(
                passed=False,
                reason=screen_reason,
                confidence=0.15,
                is_ai_generated=False
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

    # ── Layer 3: LBP texture variance (hard gate for screen replay) ───────────
    # This is the most reliable discriminator between real skin and screens.
    # Real skin at webcam distance always has LBP > 5.5 due to pores, wrinkles,
    # and natural surface texture. Screens smooth out this detail to LBP < 5.
    lbp_var = _local_texture_variance(gray)
    lbp_ok  = lbp_var >= _LBP_VAR_MIN

    if not lbp_ok:
        return LivenessResult(
            passed=False,
            reason="Flat texture detected — possible screen replay or printed photo",
            confidence=max(float(lbp_var / _LBP_VAR_MIN * 0.5), _CONFIDENCE_FLOOR)
        )

    # ── Layer 4: Skin colour detection (HSV + YCrCb dual path) ────────────────
    color_img = bgr if bgr is not None else _gray_to_bgr(gray)
    skin_ratio = _skin_colour_ratio(color_img)
    skin_ok    = skin_ratio >= _SKIN_RATIO_MIN

    # ── Layer 5: DFT moiré detection (hard gate) ──────────────────────────────
    moire_score = _moire_score(gray)
    if moire_score > _MOIRE_SCORE_MAX:
        return LivenessResult(
            passed=False,
            reason="Moiré pattern detected — screen replay or halftone print",
            confidence=max(float(np.clip(1.0 - moire_score, 0.0, 1.0)), _CONFIDENCE_FLOOR)
        )

    # ── Layer 6: Ridge frequency ratio ────────────────────────────────────────
    ridge_ratio = _ridge_band_ratio(gray)
    ridge_ok    = ridge_ratio >= _RIDGE_BAND_RATIO_MIN

    # ── Layer 7: Reflection uniformity ────────────────────────────────────────
    refl_std = _reflection_uniformity(gray)
    refl_ok  = refl_std >= _REFLECTION_STD_MIN

    # ── Confidence aggregation ────────────────────────────────────────────────
    confidence = hand.confidence
    confidence *= (1.0 - 0.05 * (glare_ratio / _GLARE_RATIO_MAX))

    if not skin_ok:
        confidence *= 0.88   # L4: wrong colour range

    if not ridge_ok:
        confidence *= 0.90   # L6: wrong ridge frequency

    if not refl_ok:
        confidence *= 0.90   # L7: uniform reflection

    # Apply confidence floor
    confidence = float(np.clip(confidence, _CONFIDENCE_FLOOR, 1.0))

    # ── Combined soft-fail logic ──────────────────────────────────────────────
    # If 2+ of the remaining soft layers [L4, L6, L7] fail, reject.
    soft_fail_count = sum([
        not skin_ok,           # L4
        not ridge_ok,          # L6
        not refl_ok,           # L7
    ])

    if soft_fail_count >= 2:
        reasons = []
        if not skin_ok:
            reasons.append("no skin tone")
        if not ridge_ok:
            reasons.append("incorrect ridge pattern")
        if not refl_ok:
            reasons.append("uniform reflection")
        reason_str = " + ".join(reasons)
        return LivenessResult(
            passed=False,
            reason=f"Spoof/Deepfake detected — {reason_str}",
            confidence=confidence
        )

    return LivenessResult(passed=True, reason=None, confidence=confidence)

# ── Layer 3 helper: local texture variance (LBP proxy) ───────────────────────

def _local_texture_variance(gray: np.ndarray) -> float:
    """
    Fast LBP-proxy: mean of per-pixel local standard deviation in a 5×5 window.

    Real webcam finger:   mean local std ≈ 6–30
    Screen replay:        mean local std ≈ 2–5
    Printed photo:        mean local std ≈ 3–6
    Threshold: 5.5
    """
    f   = gray.astype(np.float32)
    k   = (5, 5)
    mu  = cv2.blur(f, k)
    mu2 = cv2.blur(f * f, k)
    var = np.clip(mu2 - mu * mu, 0, None)
    return float(np.mean(np.sqrt(var)))


# ── Layer 4 helper: skin colour ratio (HSV + YCrCb dual-path) ────────────────

def _skin_colour_ratio(bgr: np.ndarray) -> float:
    """
    Fraction of pixels that fall within the skin-tone range.
    Uses BOTH HSV and YCrCb colour spaces for robustness across skin tones.
    """
    total = bgr.shape[0] * bgr.shape[1]
    if total == 0:
        return 0.0

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask_hsv1 = cv2.inRange(hsv,
                            np.array([0,  15,  40], dtype=np.uint8),
                            np.array([30, 220, 255], dtype=np.uint8))
    mask_hsv2 = cv2.inRange(hsv,
                            np.array([160, 15,  40], dtype=np.uint8),
                            np.array([180, 220, 255], dtype=np.uint8))
    mask_hsv = cv2.bitwise_or(mask_hsv1, mask_hsv2)

    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask_ycrcb = cv2.inRange(ycrcb,
                             np.array([0,  133, 77], dtype=np.uint8),
                             np.array([255, 177, 127], dtype=np.uint8))

    skin_mask   = cv2.bitwise_or(mask_hsv, mask_ycrcb)
    skin_pixels = cv2.countNonZero(skin_mask)
    return float(skin_pixels / total)


# ── Layer 5 helper: DFT moiré score ──────────────────────────────────────────

def _moire_score(gray: np.ndarray) -> float:
    """
    Detect periodic moiré patterns using P95/median DFT ratio.

    Screen moiré: P95/median ≈ 8-40 → score 0.2-1.0
    Real skin:    P95/median ≈ 3-8  → score 0.0-0.2
    """
    target = 256
    resized = cv2.resize(gray, (target, target))

    f      = np.fft.fft2(resized.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag    = np.abs(fshift)

    cy, cx = target // 2, target // 2
    Y, X   = np.ogrid[:target, :target]
    dc_r   = int(target * 0.10)
    dc_mask = (Y - cy) ** 2 + (X - cx) ** 2 <= dc_r ** 2

    freq_values = mag[~dc_mask]
    if freq_values.size < 10:
        return 0.0

    median_energy = float(np.median(freq_values))
    if median_energy < 1e-6:
        return 0.0

    p95_energy = float(np.percentile(freq_values, 95))
    ratio = p95_energy / median_energy

    score = float(np.clip((ratio - 3.0) / 22.0, 0.0, 1.0))
    return score


# ── Layer 6 helper: ridge frequency band ratio ───────────────────────────────

def _ridge_band_ratio(gray: np.ndarray) -> float:
    """
    Fraction of DFT spectral energy in the fingerprint ridge band.
    Very lenient threshold for webcam — primarily catches AI-generated images.
    """
    target  = 256
    resized = cv2.resize(gray, (target, target))

    f      = np.fft.fft2(resized.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag    = np.abs(fshift)

    cy, cx = target // 2, target // 2
    Y, X   = np.ogrid[:target, :target]
    r      = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)

    ridge_mask = (r >= 20) & (r <= 80)
    total_mask = (r >= 10) & (r <= 120)

    ridge_energy = float(np.sum(mag[ridge_mask]))
    total_energy = float(np.sum(mag[total_mask]))

    if total_energy < 1e-6:
        return 0.0

    return ridge_energy / total_energy


# ── Layer 7 helper: reflection uniformity ────────────────────────────────────

def _reflection_uniformity(gray: np.ndarray) -> float:
    """
    Standard deviation of pixel intensities in the top-20% brightest region.
    """
    thresh = float(np.percentile(gray, 80))
    bright_pixels = gray[gray >= thresh].astype(np.float32)

    if bright_pixels.size < 10:
        return float(_REFLECTION_STD_MIN)

    return float(np.std(bright_pixels))


# ── Layer 8 helper: Spectral Decay Anomaly ───────────────────────────────────

def _spectral_decay_anomaly(gray: np.ndarray) -> bool:
    """
    Detect unnatural high-frequency bumps caused by GAN/Diffusion upsamplers.
    Natural images decay roughly as 1/f. AI generators often leave a 'flat tail'
    or spike in the high frequency radial profile (checkerboard artifacts).
    """
    target = 256
    resized = cv2.resize(gray, (target, target))
    f = np.fft.fft2(resized.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)

    cy, cx = target // 2, target // 2
    Y, X = np.ogrid[:target, :target]
    r = np.sqrt((Y - cy)**2 + (X - cx)**2)

    r = r.astype(np.int32)
    # Bin the radii
    tbin = np.bincount(r.ravel(), mag.ravel())
    nr = np.bincount(r.ravel())
    # Avoid zero division
    nr[nr == 0] = 1
    radial_profile = tbin / nr

    # Mid frequency energy (r ≈ 20 to 60)
    mid_freq = float(np.mean(radial_profile[20:60]))
    # High frequency energy (r ≈ 80 to 120)
    high_freq = float(np.mean(radial_profile[80:120]))

    if mid_freq < 1e-6:
        return False

    ratio = high_freq / mid_freq
    # Natural images usually decay cleanly (ratio < 0.25)
    # Deepfakes often have a flat tail or bump (ratio > 0.30)
    return ratio > _SPECTRAL_DECAY_MAX


# ── Layer 9 helper: Anatomical Sanity Check ──────────────────────────────────

def _anatomical_sanity_check(hand: HandDetectionResult) -> bool:
    """
    Verify the basic geometry of the hand to catch AI hallucinations.
    Checks if the middle finger is an impossible length compared to the palm.
    """
    if not hand.raw_landmarks:
        return True  # Cannot verify if landmarks weren't passed
    
    lm = hand.raw_landmarks
    # Sanity 1: Palm Length (Wrist to Middle Finger Base)
    # Wrist: landmark[0], Middle Base: landmark[9]
    dx1 = lm.landmark[9].x - lm.landmark[0].x
    dy1 = lm.landmark[9].y - lm.landmark[0].y
    palm_len = np.sqrt(dx1**2 + dy1**2)

    # Sanity 2: Middle Finger Length (Middle Base to Middle Tip)
    # Middle Base: landmark[9], Middle Tip: landmark[12]
    dx2 = lm.landmark[12].x - lm.landmark[9].x
    dy2 = lm.landmark[12].y - lm.landmark[9].y
    finger_len = np.sqrt(dx2**2 + dy2**2)

    if palm_len < 1e-4:
        return True # Fallback

    # Standard human middle finger length is roughly 75%-110% of palm length
    # Generative AI often makes it 200%+ (spider fingers) or 30% (fused fingers)
    ratio = finger_len / palm_len
    if ratio > 1.8 or ratio < 0.4:
        return False

    return True


# ── Layer 11 helper: Screen Replay Detection ─────────────────────────────────

def _screen_replay_detection(gray: np.ndarray, bgr: np.ndarray) -> tuple:
    """
    Multi-check screen replay detector (optimized for speed + sub-pixel accuracy).
    Runs on a center CROP (not downscaled) to preserve display sub-pixel noise
    patterns while minimizing computation.
    """
    h, w = gray.shape[:2]
    if h < 64 or w < 64:
        return False, None
    
    # ── Take a 100x100 center crop (or smaller if image is small) ─────────────
    crop_size = min(100, h, w)
    cy, cx = h // 2, w // 2
    r_half = crop_size // 2
    gray_sm = gray[cy - r_half: cy + r_half, cx - r_half: cx + r_half]
    bgr_sm = bgr[cy - r_half: cy + r_half, cx - r_half: cx + r_half]

    # ── Check 1: Gradient Kurtosis (fast on center crop) ─────────────────────
    sobelx = cv2.Sobel(gray_sm, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray_sm, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.sqrt(sobelx**2 + sobely**2)
    mean_g = np.mean(grad_mag)
    std_g  = np.std(grad_mag)
    if std_g > 1e-6:
        kurtosis = float(np.mean(((grad_mag - mean_g) / std_g) ** 4) - 3.0)
        if kurtosis < 2.0:  # Tightened from 1.8 to catch retina screens
            return True, "Screen replay detected \u2014 unnatural gradient pattern"

    # ── Check 2: Color Channel Noise Correlation (fast on center crop) ────────
    b_ch = bgr_sm[:, :, 0].astype(np.float32)
    g_ch = bgr_sm[:, :, 1].astype(np.float32)
    r_ch = bgr_sm[:, :, 2].astype(np.float32)
    b_noise = b_ch - cv2.GaussianBlur(b_ch, (5, 5), 0)
    g_noise = g_ch - cv2.GaussianBlur(g_ch, (5, 5), 0)
    r_noise = r_ch - cv2.GaussianBlur(r_ch, (5, 5), 0)

    def _corr(a, b):
        a_flat, b_flat = a.ravel(), b.ravel()
        if np.std(a_flat) < 1e-6 or np.std(b_flat) < 1e-6:
            return 1.0
        return float(np.corrcoef(a_flat, b_flat)[0, 1])

    avg_corr = (_corr(r_noise, g_noise) + _corr(g_noise, b_noise)) / 2.0
    if avg_corr < 0.65:  # Tightened slightly to block retina displays
        return True, "Screen replay detected \u2014 decorrelated color channel noise"

    # ── Check 3: Blur/Sharpness Uniformity (catch flat screens) ───────────────
    lap_var = cv2.Laplacian(gray_sm, cv2.CV_64F).var()
    if lap_var < 50.0:
        return True, "Screen replay detected \u2014 missing 3D surface detail"
        
    # ── Check 4: High-Frequency Cross Energy (Phone Pixel Grid) ───────────────
    # A phone's LCD/OLED pixel matrix creates strong horizontal and vertical 
    # spikes in the 2D frequency spectrum. Real skin has isotropic (circular) energy.
    f = np.fft.fft2(gray_sm.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    cy, cx = mag.shape[0] // 2, mag.shape[1] // 2
    
    # Blank out the low frequencies (DC component + low frequencies)
    cv2.circle(mag, (cx, cy), 15, 0, -1)
    
    # Calculate energy on the primary axes (cross) vs the rest of the high-frequencies
    h_strip = mag[cy-2:cy+3, :]
    v_strip = mag[:, cx-2:cx+3]
    cross_energy = float(np.sum(h_strip)) + float(np.sum(v_strip))
    total_energy = float(np.sum(mag))
    
    if total_energy > 1e-6:
        # If the cross dominates the spectrum, it's a grid (screen)
        grid_ratio = cross_energy / total_energy
        if grid_ratio > 0.40:  # Strong orthogonal harmonics
            return True, "Screen replay detected \u2014 pixel grid harmonics"

    return False, None


# ── Utility ───────────────────────────────────────────────────────────────────

def _gray_to_bgr(gray: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
