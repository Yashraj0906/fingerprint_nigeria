from fastapi import APIRouter, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from typing import List, Optional
import cv2
import numpy as np
import tempfile
import os
from app.models.schemas import (
    CaptureRequest, CaptureResponse,
    MultiCaptureRequest, MultiCaptureResponse,
    FingerResult,
    AnalyzeRequest, AnalyzeResponse, AnalyzeFingerResult, BboxPct,
    VideoFrameResult, VideoAnalyzeResponse,
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
_FINGER_KEYS = ["THUMB", "INDEX", "MIDDLE", "RING", "LITTLE"]


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
    Each finger is quality-checked + liveness-checked + template-encoded
    independently using its own crop (not the full frame).
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

    results: List[FingerResult] = []

    for finger_key, finger_id in zip(_FINGER_KEYS, finger_ids):
        fc = hand.fingers.get(finger_key)

        # Finger not visible in frame
        if fc is None or not fc.detected or fc.crop is None:
            results.append(_failed(
                finger_id, "FINGER_NOT_DETECTED",
                "Finger not visible — spread hand wider",
                guidance="Show your fingers clearly"
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
                orientation_score=round(q.orientation_score, 2),
                liveness_passed=False, liveness_confidence=None,
                template=None, enhanced_image_b64=enhanced_img_b64,
                error_code="QUALITY_LOW",
                error_message=f"Quality {q.score:.1f} below threshold",
                guidance_message=q.guidance_message
            ))
            continue

        # ── FIX: Liveness runs on finger crop, not full frame ─────────────────
        liveness = liveness_detector.evaluate(roi_gray, hand, roi_bgr)

        if not liveness.passed:
            results.append(FingerResult(
                finger_id=finger_id, status="failed",
                quality_score=round(q.score, 2),
                blur_score=round(q.blur_score, 2),
                contrast_score=round(q.contrast_score, 2),
                ridge_score=round(q.ridge_score, 2),
                coverage_score=round(q.coverage_score, 2),
                orientation_score=round(q.orientation_score, 2),
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
                orientation_score=round(q.orientation_score, 2),
                liveness_passed=True,
                liveness_confidence=round(liveness.confidence, 3),
                is_ai_generated=False,
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
            is_ai_generated=False,
            template=template, enhanced_image_b64=enhanced_img_b64,
            error_code=None, error_message=None,
            guidance_message=None
        ))

    success_count = sum(1 for r in results if r.status == "success")
    overall = "success" if success_count == 4 \
        else "partial" if success_count > 0 else "failed"

    # Aggregate guidance: worst finger first
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

    FIX: Liveness is evaluated per finger crop (not the full frame).
    This prevents JPEG block artifacts and background pixels from
    triggering the moiré hard-gate and collapsing LBP texture scores.
    """
    hand_prefix = request.hand.upper()

    try:
        bgr = image_processor.base64_to_mat(request.image_base64)
    except Exception as e:
        return AnalyzeResponse(hand_detected=False, hand=request.hand,
                               guidance="Image decode failed", fingers=[])

    h_img, w_img = bgr.shape[:2]
    
    # ── HARD SCREEN BLOCK: Detect physical rectangular phone ───────────────
    gray_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray_full, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    cnts, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    screen_bezel_detected = False
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        # Look for a large 4-sided polygon (phone bounding box)
        if len(approx) == 4 and cv2.contourArea(approx) > (w_img * h_img * 0.15):
            screen_bezel_detected = True
            break
            
    if screen_bezel_detected:
        return AnalyzeResponse(hand_detected=True, hand=request.hand,
                               guidance="Screen replay detected \u2014 phone border found", fingers=[])

    hand = hand_detector.detect_all_fingers(bgr)

    if not hand.detected:
        return AnalyzeResponse(hand_detected=False, hand=request.hand,
                               guidance=hand.guidance or "No hand detected", fingers=[])

    fingers_out = []

    for finger_key in _FINGER_KEYS:
        finger_id = f"{hand_prefix}_{finger_key}"
        fc = hand.fingers.get(finger_key)

        if fc is None or not fc.detected or fc.crop is None:
            fingers_out.append(AnalyzeFingerResult(
                finger_id=finger_id, detected=False,
                quality_score=0.0, blur_score=None, illum_score=None,
                liveness=False, liveness_conf=None,
                is_ai_generated=False,
                guidance="Finger not visible", bbox_pct=None
            ))
            continue

        # ── FIX: use finger crop for both quality AND liveness ────────────────
        roi_bgr  = fc.crop
        roi_gray = image_processor.to_gray(roi_bgr)

        q        = quality_analyzer.analyze(roi_gray)
        liveness = liveness_detector.evaluate(roi_gray, hand, roi_bgr, request.mode)

        bbox_pct = None
        if fc.bbox:
            x, y, w, h = fc.bbox
            bbox_pct = BboxPct(
                x=round(x / w_img, 4), y=round(y / h_img, 4),
                w=round(w / w_img, 4), h=round(h / h_img, 4)
            )

        # Use liveness failure reason as guidance when liveness fails,
        # otherwise use quality guidance
        if liveness.passed:
            finger_guidance = q.guidance_message
        else:
            finger_guidance = liveness.reason or q.guidance_message

        fingers_out.append(AnalyzeFingerResult(
            finger_id=finger_id, detected=True,
            quality_score=round(q.score, 2),
            blur_score=round(q.blur_score, 2),
            illum_score=round(q.contrast_score, 2),
            liveness=liveness.passed,
            liveness_conf=round(liveness.confidence, 3),
            is_ai_generated=liveness.is_ai_generated,
            guidance=finger_guidance,
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


# ── Live WebSocket Streaming Endpoint (Flutter true real-time) ───────────────

@router.websocket("/capture/stream")
async def capture_stream(websocket: WebSocket, hand: str = "RIGHT"):
    """
    True live camera streaming endpoint.
    Flutter app streams base64 frames here, and receives AnalyzeResponse JSON instantly for every frame.
    No video file is saved or transmitted as a bulk file.
    """
    await websocket.accept()
    hand_prefix = hand.upper()
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Clean up data if it has prefix
            if "," in data:
                data = data.split(",", 1)[-1]
            try:
                bgr = image_processor.from_base64(data)
            except Exception:
                await websocket.send_json({"error": "Invalid base64 payload"})
                continue

            h_img, w_img = bgr.shape[:2]
            hand_result = hand_detector.detect_all_fingers(bgr)

            fingers_out = []
            if hand_result.detected:
                for finger_key in _FINGER_KEYS:
                    finger_id = f"{hand_prefix}_{finger_key}"
                    fc = hand_result.fingers.get(finger_key)

                    if fc is None or not fc.detected or fc.crop is None:
                        fingers_out.append(AnalyzeFingerResult(
                            finger_id=finger_id, detected=False,
                            quality_score=0.0, blur_score=None, illum_score=None,
                            liveness=False, liveness_conf=None,
                            is_ai_generated=False,
                            guidance="Finger not visible", bbox_pct=None
                        ))
                        continue

                    roi_bgr  = fc.crop
                    roi_gray = image_processor.to_gray(roi_bgr)
                    q        = quality_analyzer.analyze(roi_gray)
                    liveness = liveness_detector.evaluate(roi_gray, hand_result, roi_bgr)

                    bbox_pct = None
                    if fc.bbox:
                        x, y, w, h = fc.bbox
                        bbox_pct = BboxPct(
                            x=round(x / w_img, 4), y=round(y / h_img, 4),
                            w=round(w / w_img, 4), h=round(h / h_img, 4)
                        )

                    finger_guidance = liveness.reason if not liveness.passed else q.guidance_message

                    fingers_out.append(AnalyzeFingerResult(
                        finger_id=finger_id, detected=True,
                        quality_score=round(q.score, 2),
                        blur_score=round(q.blur_score, 2),
                        illum_score=round(q.contrast_score, 2),
                        liveness=liveness.passed,
                        liveness_conf=round(liveness.confidence, 3),
                        is_ai_generated=liveness.is_ai_generated,
                        guidance=finger_guidance,
                        bbox_pct=bbox_pct
                    ))

            guidance = hand_result.guidance if hand_result.detected else "No hand detected"

            resp = AnalyzeResponse(
                hand_detected=hand_result.detected,
                hand=hand_prefix,
                guidance=guidance,
                fingers=fingers_out
            )
            
            await websocket.send_json(resp.model_dump() if hasattr(resp, 'model_dump') else resp.dict())

    except WebSocketDisconnect:
        pass  # Client closed stream gracefully


# ── Video analyze endpoint (upload a video, auto-extract best frame) ───────────

@router.post("/capture/analyze-video", response_model=AnalyzeResponse)
async def analyze_video(
    video: UploadFile = File(..., description="Video file of the hand (.mp4, .avi, .mov)"),
    hand: str = Form(default="RIGHT", description="RIGHT or LEFT"),
):
    """
    Upload a video of a hand. The engine extracts frames, runs MediaPipe
    hand detection + 10-layer liveness on each, and returns per-frame
    results plus the single best frame.
    """
    hand_prefix = hand.upper()

    # Save uploaded video to a temp file so OpenCV can read it
    suffix = os.path.splitext(video.filename or ".mp4")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await video.read())
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return VideoAnalyzeResponse(
                total_frames=0, frames_analyzed=0,
                best_frame=None, all_frames=[],
                summary="Failed to open video file"
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Sample 1 frame every 0.5 seconds (skip redundant frames)
        sample_interval = max(1, int(fps * 0.5))

        frame_results = []
        best_frame = None
        best_score = -1
        frame_idx = 0

        while True:
            ret, bgr = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval != 0:
                frame_idx += 1
                continue

            timestamp = frame_idx / fps
            h_img, w_img = bgr.shape[:2]
            hand_result = hand_detector.detect_all_fingers(bgr)

            fingers_out = []
            if hand_result.detected:
                for finger_key in _FINGER_KEYS:
                    finger_id = f"{hand_prefix}_{finger_key}"
                    fc = hand_result.fingers.get(finger_key)

                    if fc is None or not fc.detected or fc.crop is None:
                        fingers_out.append(AnalyzeFingerResult(
                            finger_id=finger_id, detected=False,
                            quality_score=0.0, blur_score=None, illum_score=None,
                            liveness=False, liveness_conf=None,
                            is_ai_generated=False,
                            guidance="Finger not visible", bbox_pct=None
                        ))
                        continue

                    roi_bgr  = fc.crop
                    roi_gray = image_processor.to_gray(roi_bgr)
                    q        = quality_analyzer.analyze(roi_gray)
                    liveness = liveness_detector.evaluate(roi_gray, hand_result, roi_bgr)

                    bbox_pct = None
                    if fc.bbox:
                        x, y, w, h = fc.bbox
                        bbox_pct = BboxPct(
                            x=round(x / w_img, 4), y=round(y / h_img, 4),
                            w=round(w / w_img, 4), h=round(h / h_img, 4)
                        )

                    finger_guidance = liveness.reason if not liveness.passed else q.guidance_message

                    fingers_out.append(AnalyzeFingerResult(
                        finger_id=finger_id, detected=True,
                        quality_score=round(q.score, 2),
                        blur_score=round(q.blur_score, 2),
                        illum_score=round(q.contrast_score, 2),
                        liveness=liveness.passed,
                        liveness_conf=round(liveness.confidence, 3),
                        is_ai_generated=liveness.is_ai_generated,
                        guidance=finger_guidance,
                        bbox_pct=bbox_pct
                    ))

            guidance = hand_result.guidance if hand_result.detected else "No hand detected"

            frame_res = VideoFrameResult(
                frame_number=frame_idx,
                timestamp_sec=round(timestamp, 2),
                hand_detected=hand_result.detected,
                fingers=fingers_out,
                guidance=guidance
            )
            frame_results.append(frame_res)

            # Score this frame: count of fingers that passed liveness
            live_count = sum(1 for f in fingers_out if f.liveness)
            avg_quality = (sum(f.quality_score for f in fingers_out if f.detected) /
                          max(1, sum(1 for f in fingers_out if f.detected)))
            frame_score = live_count * 100 + avg_quality

            if frame_score > best_score:
                best_score = frame_score
                best_frame = frame_res

            frame_idx += 1

        cap.release()

        if best_frame is None:
            return AnalyzeResponse(
                hand_detected=False,
                hand=hand_prefix,
                guidance="No valid frames could be analyzed",
                fingers=[]
            )

        return AnalyzeResponse(
            hand_detected=best_frame.hand_detected,
            hand=hand_prefix,
            guidance=best_frame.guidance,
            fingers=best_frame.fingers
        )
    finally:
        os.unlink(tmp_path)


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

    hand = hand_detector.detect_finger(bgr)

    if not hand.detected:
        return _failed(finger_id, "NO_FINGER_DETECTED",
                       hand.guidance or "No hand detected",
                       guidance=hand.guidance)

    # ── FIX: use crop for quality AND liveness, not full frame ────────────────
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

    # Liveness on finger crop — not the full frame
    liveness = liveness_detector.evaluate(roi_gray, hand, roi_bgr)

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
