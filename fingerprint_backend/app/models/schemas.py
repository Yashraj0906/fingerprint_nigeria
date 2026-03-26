from pydantic import BaseModel
from typing import Optional, List


# ── Capture (single finger) ────────────────────────────────────────────────────

class FingerImage(BaseModel):
    finger_id:    str
    image_base64: str


class CaptureRequest(BaseModel):
    transaction_id: str
    fingers:        List[FingerImage]


class FingerResult(BaseModel):
    finger_id:           str
    status:              str              # success | failed
    quality_score:       float
    blur_score:          Optional[float]
    contrast_score:      Optional[float]
    ridge_score:         Optional[float]
    coverage_score:      Optional[float]
    liveness_passed:     bool
    liveness_confidence: Optional[float]
    template:            Optional[str]    # base64 ISO 19794-2, None if failed
    error_code:          Optional[str]
    error_message:       Optional[str]
    guidance_message:    Optional[str]    # human-readable fix hint for live UI


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
