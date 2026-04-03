from pydantic import BaseModel
from typing import Optional, List


# ── Capture (single finger) ────────────────────────────────────────────────────

class FingerImage(BaseModel):
    finger_id:    str
    image_base64: str


class CaptureRequest(BaseModel):
    transaction_id: str
    fingers:        List[FingerImage]


class BboxPct(BaseModel):
    x: float   # left edge as fraction of image width  (0-1)
    y: float   # top  edge as fraction of image height (0-1)
    w: float   # width  as fraction of image width
    h: float   # height as fraction of image height


class FingerResult(BaseModel):
    finger_id:           str
    status:              str              # success | failed
    quality_score:       float
    blur_score:          Optional[float]
    contrast_score:      Optional[float]
    ridge_score:         Optional[float]
    coverage_score:      Optional[float]
    orientation_score:   Optional[float] = None
    liveness_passed:     bool
    liveness_confidence: Optional[float]
    is_ai_generated:     bool             = False
    template:            Optional[str]    # base64 ISO 19794-2, None if failed
    enhanced_image_b64:  Optional[str]   = None  # CLAHE-enhanced grayscale crop for UI display
    error_code:          Optional[str]
    error_message:       Optional[str]
    guidance_message:    Optional[str]    # human-readable fix hint for live UI
    bbox_pct:            Optional[BboxPct] = None  # finger crop location in image


# ── Fast analyze (no template encoding) ──────────────────────────────────────

class AnalyzeRequest(BaseModel):
    image_base64: str
    hand:         str   # "RIGHT" | "LEFT"
    mode:         str = ""  # The exact dropdown value (e.g., "RIGHT_THUMB")


class AnalyzeFingerResult(BaseModel):
    finger_id:    str
    detected:     bool
    quality_score: float
    blur_score:   Optional[float]
    illum_score:  Optional[float]   # contrast_score
    liveness:     bool
    liveness_conf: Optional[float]
    is_ai_generated: bool = False
    guidance:     Optional[str]
    bbox_pct:     Optional[BboxPct]


class AnalyzeResponse(BaseModel):
    hand_detected: bool
    hand:          str
    guidance:      Optional[str]
    fingers:       List[AnalyzeFingerResult]


# ── Video analyze ─────────────────────────────────────────────────────────────

class VideoFrameResult(BaseModel):
    frame_number:  int
    timestamp_sec: float
    hand_detected: bool
    fingers:       List[AnalyzeFingerResult]
    guidance:      Optional[str]


class VideoAnalyzeResponse(BaseModel):
    total_frames:    int
    frames_analyzed: int
    best_frame:      Optional[VideoFrameResult]
    all_frames:      List[VideoFrameResult]
    summary:         str


class CaptureResponse(BaseModel):
    transaction_id: str
    overall_status: str                   # success | partial | failed
    results:        List[FingerResult]


# ── Multi-finger slap capture ──────────────────────────────────────────────────

class MultiCaptureRequest(BaseModel):
    transaction_id: str
    image_base64:   str
    hand:           str                   # "RIGHT" or "LEFT"


class MultiCaptureResponse(BaseModel):
    transaction_id: str
    overall_status: str                   # success | partial | failed
    hand:           str
    guidance:       Optional[str]         # real-time positioning hint
    results:        List[FingerResult]


# ── Enroll ────────────────────────────────────────────────────────────────────

class EnrollFinger(BaseModel):
    finger_id:     str
    template:      str                    # base64 ISO 19794-2
    quality_score: float


class EnrollRequest(BaseModel):
    user_id:        str
    transaction_id: str
    fingers:        List[EnrollFinger]


class EnrollResponse(BaseModel):
    enrollment_id:    str
    user_id:          str
    status:           str                 # enrolled | updated
    fingers_enrolled: List[str]


# ── Verify ────────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    user_id:        str
    transaction_id: str
    fingers:        List[FingerImage]


class VerifyResponse(BaseModel):
    transaction_id: str
    user_id:        str
    match:          bool
    confidence:     float                 # 0.0 – 1.0
    message:        str
