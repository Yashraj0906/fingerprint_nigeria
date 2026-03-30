from fastapi import APIRouter
from typing import List, Optional
from app.models.schemas import (
    CaptureRequest, CaptureResponse,
    MultiCaptureRequest, MultiCaptureResponse,
    FingerResult,
    AnalyzeRequest, AnalyzeResponse, AnalyzeFingerResult, BboxPct,
)
from app.services import image_processor, quality_analyzer, liveness_detector, template_encoder
from app.services import hand_detector

router = APIRouter()

# ISO 19794-2 finger position codes
_FINGER_POSITION = {
    "RIGHT_THUMB": 1, "RIGHT_INDEX": 2, "RIGHT_MIDDLE": 3,
    "RIGHT_RING":  4, "RIGHT_LITTLE": 5,
    "LEFT_THUMB":  6, "LEFT_INDEX":  7, "LEFT_MIDDLE":  8,
    "LEFT_RING":   9, "LEFT_LITTLE": 10,
}

# Finger key → full ID suffix
_FINGER_KEYS = ["INDEX", "MIDDLE", "RING", "LITTLE"]


# ── Single-finger endpoint (existing) ─────────────────────────────────────────

@router.post("/capture/process", response_model=CaptureResponse)
def process_capture(request: CaptureRequest):
    """
    Phase 2 single-finger endpoint.
    Accepts one or more finger images, returns per-finger results.
    """
    results: List[FingerResult] = []

    for finger in request.fingers:
        results.append(_process_single(finger.finger_id, finger.image_base64))

    success_count = sum(1 for r in results if r.status == "success")
    overall = "success" if success_count == len(results) \
        else "partial" if success_count > 0 else "failed"

    return CaptureResponse(
        transaction_id=request.transaction_id,
        overall_status=overall,
        results=results
    )


# ── 4-finger slap capture endpoint (new) ──────────────────────────────────────

@router.post("/capture/multi", response_model=MultiCaptureResponse)
def process_multi_capture(request: MultiCaptureRequest):
    """
    4-finger slap capture (index, middle, ring, little of one hand).

    Accepts a single frame + hand side ("RIGHT" | "LEFT").
    MediaPipe detects all 4 fingers and extracts individual crops.
    Each finger is quality-checked + template-encoded independently.
    """
    hand_prefix = request.hand.upper()  # "RIGHT" or "LEFT"
    finger_ids  = [f"{hand_prefix}_{k}" for k in _FINGER_KEYS]

    # ── Decode image ──────────────────────────────────────────────────────────
    try:
        bgr = image_processor.base64_to_mat(request.image_base64)
    except Exception as e:
        results = [_failed(fid, "DECODE_ERROR", str(e)) for fid in finger_ids]
        return MultiCaptureResponse(
            transaction_id=request.transaction_id,
            overall_status="failed", hand=request.hand,
            guidance="Image decode failed", results=results
        )

    gray = image_processor.to_gray(bgr)

    # ── Hand detection ────────────────────────────────────────────────────────
    hand = hand_detector.detect_all_fingers(bgr)

    if not hand.detected:
        results = [_failed(fid, "NO_HAND_DETECTED",
                           "No hand detected — place your hand in the frame",
                           guidance=hand.guidance)
                   for fid in finger_ids]
        return MultiCaptureResponse(
            transaction_id=request.transaction_id,
            overall_status="failed", hand=request.hand,
            guidance=hand.guidance, results=results
        )

    # Liveness is per-hand (one check for all 4 fingers)
    liveness = liveness_detector.evaluate(gray, hand, bgr)

    results: List[FingerResult] = []

    for finger_key, finger_id in zip(_FINGER_KEYS, finger_ids):
        fc = hand.fingers.get(finger_key)

        # Finger not visible in frame
        if fc is None or not fc.detected or fc.crop is None:
            results.append(_failed(
                finger_id, "FINGER_NOT_DETECTED",
                "Finger not visible — spread hand wider",
                guidance="Show all 4 fingers clearly"
            ))
            continue

        roi_bgr  = fc.crop
        roi_gray = image_processor.to_gray(roi_bgr)

        # Enhanced visual crop — always generated so UI can show a clean thumbnail
        enhanced_crop    = image_processor.enhance_visual(roi_bgr)
        enhanced_img_b64 = image_processor.mat_to_base64(enhanced_crop, quality=88)

        # Quality check
        q = quality_analyzer.analyze(roi_gray)

        if q.verdict == quality_analyzer.Verdict.REJECT:
            results.append(FingerResult(
                finger_id=finger_id, status="failed",
                quality_score=round(q.score, 2),
                blur_score=round(q.blur_score, 2),
                contrast_score=round(q.contrast_score, 2),
                ridge_score=round(q.ridge_score, 2),
                coverage_score=round(q.coverage_score, 2),
                liveness_passed=False, liveness_confidence=None,
                template=None, enhanced_image_b64=enhanced_img_b64,
                error_code="QUALITY_LOW",
                error_message=f"Quality {q.score:.1f} below threshold",
                guidance_message=q.guidance_message
            ))
            continue

        # Liveness check
        if not liveness.passed:
            results.append(FingerResult(
                finger_id=finger_id, status="failed",
                quality_score=round(q.score, 2),
                blur_score=round(q.blur_score, 2),
                contrast_score=round(q.contrast_score, 2),
                ridge_score=round(q.ridge_score, 2),
                coverage_score=round(q.coverage_score, 2),
                liveness_passed=False,
                liveness_confidence=round(liveness.confidence, 3),
                template=None, enhanced_image_b64=enhanced_img_b64,
                error_code="LIVENESS_FAILED",
                error_message=liveness.reason or "Liveness check failed",
                guidance_message=None
            ))
            continue

        # Template generation
        skeleton   = image_processor.enhance(roi_bgr)
        finger_pos = _FINGER_POSITION.get(finger_id.upper(), 0)
        template   = template_encoder.encode(skeleton, finger_pos, q.score)

        if template is None:
            results.append(FingerResult(
                finger_id=finger_id, status="failed",
                quality_score=round(q.score, 2),
                blur_score=round(q.blur_score, 2),
                contrast_score=round(q.contrast_score, 2),
                ridge_score=round(q.ridge_score, 2),
                coverage_score=round(q.coverage_score, 2),
                liveness_passed=True,
                liveness_confidence=round(liveness.confidence, 3),
                template=None, enhanced_image_b64=enhanced_img_b64,
                error_code="LOW_RIDGE_DETAIL",
                error_message="Insufficient ridge detail",
                guidance_message="Flatten finger slightly — ridges unclear"
            ))
            continue

        results.append(FingerResult(
            finger_id=finger_id, status="success",
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            contrast_score=round(q.contrast_score, 2),
            ridge_score=round(q.ridge_score, 2),
            coverage_score=round(q.coverage_score, 2),
            liveness_passed=True,
            liveness_confidence=round(liveness.confidence, 3),
            template=template, enhanced_image_b64=enhanced_img_b64,
            error_code=None, error_message=None,
            guidance_message=None
        ))

    success_count = sum(1 for r in results if r.status == "success")
    overall = "success" if success_count == 4 \
        else "partial" if success_count > 0 else "failed"

    # Aggregate guidance: hand-level first, then worst finger
    guidance = hand.guidance
    if not guidance:
        for r in results:
            if r.guidance_message:
                guidance = r.guidance_message
                break

    return MultiCaptureResponse(
        transaction_id=request.transaction_id,
        overall_status=overall, hand=request.hand,
        guidance=guidance, results=results
    )


# ── Fast analyze endpoint (no template — just detection + quality + bboxes) ───

@router.post("/capture/analyze", response_model=AnalyzeResponse)
def analyze_frame(request: AnalyzeRequest):
    """
    Lightweight real-time analysis endpoint for the live UI.
    Runs MediaPipe hand detection + quality scoring on each frame.
    Returns per-finger quality scores and bounding boxes (as % of image size).
    Does NOT encode templates — fast enough for 5-10 fps polling.
    """
    hand_prefix = request.hand.upper()

    try:
        bgr = image_processor.base64_to_mat(request.image_base64)
    except Exception as e:
        return AnalyzeResponse(hand_detected=False, hand=request.hand,
                               guidance="Image decode failed", fingers=[])

    h_img, w_img = bgr.shape[:2]
    gray = image_processor.to_gray(bgr)
    hand = hand_detector.detect_all_fingers(bgr)

    if not hand.detected:
        return AnalyzeResponse(hand_detected=False, hand=request.hand,
                               guidance=hand.guidance or "No hand detected", fingers=[])

    liveness = liveness_detector.evaluate(gray, hand, bgr)
    fingers_out = []

    for finger_key in _FINGER_KEYS:
        finger_id = f"{hand_prefix}_{finger_key}"
        fc = hand.fingers.get(finger_key)

        if fc is None or not fc.detected or fc.crop is None:
            fingers_out.append(AnalyzeFingerResult(
                finger_id=finger_id, detected=False,
                quality_score=0.0, blur_score=None, illum_score=None,
                liveness=False, liveness_conf=None,
                guidance="Finger not visible", bbox_pct=None
            ))
            continue

        roi_gray = image_processor.to_gray(fc.crop)
        q = quality_analyzer.analyze(roi_gray)

        bbox_pct = None
        if fc.bbox:
            x, y, w, h = fc.bbox
            bbox_pct = BboxPct(
                x=round(x / w_img, 4), y=round(y / h_img, 4),
                w=round(w / w_img, 4), h=round(h / h_img, 4)
            )

        fingers_out.append(AnalyzeFingerResult(
            finger_id=finger_id, detected=True,
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            illum_score=round(q.contrast_score, 2),
            liveness=liveness.passed,
            liveness_conf=round(liveness.confidence, 3),
            guidance=q.guidance_message,
            bbox_pct=bbox_pct
        ))

    overall_guidance = hand.guidance
    if not overall_guidance:
        for f in fingers_out:
            if f.guidance:
                overall_guidance = f.guidance
                break

    return AnalyzeResponse(
        hand_detected=True, hand=request.hand,
        guidance=overall_guidance, fingers=fingers_out
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _failed(finger_id: str, error_code: str, error_message: str,
            guidance: Optional[str] = None) -> FingerResult:
    return FingerResult(
        finger_id=finger_id, status="failed",
        quality_score=0.0, blur_score=None, contrast_score=None,
        ridge_score=None, coverage_score=None,
        liveness_passed=False, liveness_confidence=None,
        template=None, error_code=error_code, error_message=error_message,
        guidance_message=guidance
    )


def _process_single(finger_id: str, image_base64: str) -> FingerResult:
    """Single-finger processing pipeline (used by /capture/process)."""
    try:
        bgr = image_processor.base64_to_mat(image_base64)
    except Exception as e:
        return _failed(finger_id, "DECODE_ERROR", str(e))

    gray = image_processor.to_gray(bgr)
    hand = hand_detector.detect_finger(bgr)

    if not hand.detected:
        return _failed(finger_id, "NO_FINGER_DETECTED",
                       hand.guidance or "No hand detected",
                       guidance=hand.guidance)

    roi_bgr  = hand.finger_crop if hand.finger_crop is not None else bgr
    roi_gray = image_processor.to_gray(roi_bgr)
    q        = quality_analyzer.analyze(roi_gray)

    if q.verdict == quality_analyzer.Verdict.REJECT:
        return FingerResult(
            finger_id=finger_id, status="failed",
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            contrast_score=round(q.contrast_score, 2),
            ridge_score=round(q.ridge_score, 2),
            coverage_score=round(q.coverage_score, 2),
            liveness_passed=False, liveness_confidence=None,
            template=None, error_code="QUALITY_LOW",
            error_message=f"Quality {q.score:.1f} below threshold",
            guidance_message=q.guidance_message
        )

    liveness = liveness_detector.evaluate(gray, hand, bgr)

    if not liveness.passed:
        return FingerResult(
            finger_id=finger_id, status="failed",
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            contrast_score=round(q.contrast_score, 2),
            ridge_score=round(q.ridge_score, 2),
            coverage_score=round(q.coverage_score, 2),
            liveness_passed=False,
            liveness_confidence=round(liveness.confidence, 3),
            template=None, error_code="LIVENESS_FAILED",
            error_message=liveness.reason or "Liveness check failed",
            guidance_message=None
        )

    skeleton   = image_processor.enhance(roi_bgr)
    finger_pos = _FINGER_POSITION.get(finger_id.upper(), 0)
    template   = template_encoder.encode(skeleton, finger_pos, q.score)

    if template is None:
        return FingerResult(
            finger_id=finger_id, status="failed",
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            contrast_score=round(q.contrast_score, 2),
            ridge_score=round(q.ridge_score, 2),
            coverage_score=round(q.coverage_score, 2),
            liveness_passed=True,
            liveness_confidence=round(liveness.confidence, 3),
            template=None, error_code="LOW_RIDGE_DETAIL",
            error_message="Insufficient ridge detail for template generation",
            guidance_message="Flatten finger slightly — ridges unclear"
        )

    return FingerResult(
        finger_id=finger_id, status="success",
        quality_score=round(q.score, 2),
        blur_score=round(q.blur_score, 2),
        contrast_score=round(q.contrast_score, 2),
        ridge_score=round(q.ridge_score, 2),
        coverage_score=round(q.coverage_score, 2),
        liveness_passed=True,
        liveness_confidence=round(liveness.confidence, 3),
        template=template, error_code=None, error_message=None,
        guidance_message=None
    )
