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

def _gabor_bank_enhance(gray: np.ndarray) -> np.ndarray:
    """
    True Gabor filter bank for fingerprint ridge enhancement.

    WHY GABOR (vs previous Sobel projection):
    - Gabor = sinusoidal carrier modulated by Gaussian envelope — it's a
      matched filter for the periodic ridge pattern at a specific frequency.
    - Sobel just detects edges in one direction; it has no notion of ridge
      periodicity, so it enhances all edges equally (noise, skin creases, etc.).
    - Gabor at the right wavelength suppresses noise and non-ridge texture while
      amplifying the regular ridge-valley alternation.

    PARAMETERS (tuned for contactless webcam at 30-50 cm, HD resolution):
    - lambd = 9 px  ← typical ridge pitch at this camera-to-finger distance
    - sigma = 3.5   ← Gaussian envelope width (covers ~1 ridge period)
    - gamma = 0.5   ← spatial aspect ratio (elongated along ridge direction)
    - 8 orientations spanning 0°–157.5° covers all possible ridge angles
    """
    ksize  = 21
    sigma  = 3.5
    lambd  = 9.0
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
