import cv2
import numpy as np
import base64


def base64_to_mat(b64_string: str) -> np.ndarray:
    img_data = base64.b64decode(b64_string)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image from base64 string")
    return img


def mat_to_base64(mat: np.ndarray, quality: int = 85) -> str:
    _, buffer = cv2.imencode('.jpg', mat, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buffer).decode('utf-8')


def to_gray(src: np.ndarray) -> np.ndarray:
    if len(src.shape) == 3:
        return cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    return src.copy()


def enhance_visual(src: np.ndarray) -> np.ndarray:
    """
    Lightweight visual enhancement for UI display.
    Returns a clean CLAHE-enhanced grayscale image (not skeletonized).
    Bilateral filter removes webcam compression noise while keeping ridge edges sharp.
    """
    gray     = to_gray(src)
    denoised = cv2.bilateralFilter(gray, 9, 50, 50)
    clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def enhance(src: np.ndarray) -> np.ndarray:
    """
    Full enhancement pipeline:
      Grayscale → Bilateral denoise → CLAHE → Gabor bank → Adaptive threshold → Morph cleanup → Skeleton
    """
    gray = to_gray(src)

    # Bilateral filter: removes JPEG/webcam compression noise while preserving ridge edges
    denoised = cv2.bilateralFilter(gray, 9, 50, 50)

    clahe     = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    clahe_out = clahe.apply(denoised)

    ridge_enhanced = _gabor_bank_enhance(clahe_out)

    binary = cv2.adaptiveThreshold(
        ridge_enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological cleanup: remove isolated noise pixels before skeletonization
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    return _skeletonize(binary)


def detect_ridges(gray: np.ndarray) -> np.ndarray:
    return cv2.Canny(gray, 40, 120, apertureSize=3)


# ── Private helpers ───────────────────────────────────────────────────────────

def _estimate_ridge_frequency(gray: np.ndarray) -> float:
    """
    Estimate dominant ridge wavelength λ (pixels) via FFT of a central row strip.

    WHY THIS MATTERS:
    At 25 cm from a webcam the ridge pitch is ~7 px; at 45 cm it's ~14 px.
    A Gabor filter tuned to the wrong frequency suppresses the very ridges it
    should enhance.  Measuring the actual frequency and adapting λ per-image
    keeps the filter matched regardless of capture distance.

    METHOD:
    - Average a horizontal strip through the image centre → 1-D signal
    - Remove DC trend, compute RFFT magnitude
    - Search for the dominant peak in the 5-18 px wavelength band
    - Require peak ≥ 2× median of that band (SNR guard) before accepting
    - Fall back to 9.0 px if the image is too uniform or noisy to measure
    """
    h, w = gray.shape
    r1 = h // 3
    r2 = 2 * h // 3
    strip = gray[r1:r2, :].mean(axis=0).astype(np.float32)
    strip -= strip.mean()

    if len(strip) < 16:
        return 9.0

    fft_mag = np.abs(np.fft.rfft(strip))
    freqs   = np.fft.rfftfreq(len(strip))

    # Frequency band corresponding to 5-18 px ridge pitch
    mask = (freqs >= 1.0 / 18.0) & (freqs <= 1.0 / 5.0)
    if not mask.any():
        return 9.0

    band       = fft_mag[mask]
    peak_val   = float(band.max())
    noise_val  = float(np.median(band))

    if noise_val < 1e-6 or peak_val / noise_val < 2.0:
        return 9.0  # no clear dominant frequency — fall back

    peak_freq = float(freqs[mask][np.argmax(band)])
    if peak_freq < 1e-6:
        return 9.0

    return float(np.clip(1.0 / peak_freq, 5.0, 18.0))


def _gabor_bank_enhance(gray: np.ndarray) -> np.ndarray:
    """
    Adaptive Gabor filter bank for fingerprint ridge enhancement.

    Uses _estimate_ridge_frequency() to measure the actual ridge pitch in
    the current image and tunes λ accordingly.  Falls back to 9 px when the
    frequency cannot be reliably estimated.

    8 orientations at 22.5° intervals cover every possible ridge direction.
    sigma is set to 0.56 * λ so the Gaussian envelope spans ~1 ridge period,
    matching the filter bandwidth to the signal.
    """
    lambd  = _estimate_ridge_frequency(gray)
    sigma  = lambd * 0.56   # envelope ≈ 1 ridge period wide
    ksize  = int(2 * round(3 * sigma) + 1)   # kernel spans ±3σ, always odd
    ksize  = max(ksize, 11)
    gamma  = 0.5
    psi    = 0.0

    result = np.zeros(gray.shape, dtype=np.float32)
    for theta in np.linspace(0, np.pi, 8, endpoint=False):
        kernel   = cv2.getGaborKernel(
            (ksize, ksize), sigma, theta, lambd, gamma, psi, ktype=cv2.CV_32F
        )
        filtered = cv2.filter2D(gray.astype(np.float32), cv2.CV_32F, kernel)
        result   = np.maximum(result, np.abs(filtered))

    return cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)


def _skeletonize(binary: np.ndarray) -> np.ndarray:
    skeleton = np.zeros(binary.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    src = binary.copy()

    while True:
        eroded = cv2.erode(src, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(src, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        src = eroded.copy()
        if cv2.countNonZero(src) == 0:
            break

    return skeleton
