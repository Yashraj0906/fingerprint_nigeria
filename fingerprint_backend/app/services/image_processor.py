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


def enhance(src: np.ndarray) -> np.ndarray:
    """
    Full enhancement pipeline:
      Grayscale → CLAHE → Gaussian → Gabor-bank (Sobel) → Adaptive threshold → Skeleton
    """
    gray = to_gray(src)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    clahe_out = clahe.apply(gray)

    blurred = cv2.GaussianBlur(clahe_out, (3, 3), 1.0)

    ridge_enhanced = _gabor_bank_enhance(blurred)

    binary = cv2.adaptiveThreshold(
        ridge_enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    return _skeletonize(binary)


def detect_ridges(gray: np.ndarray) -> np.ndarray:
    return cv2.Canny(gray, 40, 120, apertureSize=3)


# ── Private helpers ───────────────────────────────────────────────────────────

def _gabor_bank_enhance(gray: np.ndarray) -> np.ndarray:
    """
    Multi-angle ridge enhancement using Sobel gradients at 0°, 45°, 90°, 135°.
    Computes gx and gy once, then projects onto each angle direction.
    """
    temp32 = gray.astype(np.float32)
    gx = cv2.Sobel(temp32, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(temp32, cv2.CV_32F, 0, 1, ksize=3)

    result = np.zeros(gray.shape, dtype=np.float32)
    for angle_deg in [0, 45, 90, 135]:
        theta    = np.radians(angle_deg)
        response = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
        result   = np.maximum(result, response)

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
