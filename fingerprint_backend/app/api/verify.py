from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User, Enrollment, FingerTemplate
from app.models.schemas import VerifyRequest, VerifyResponse
from app.services import image_processor, quality_analyzer, liveness_detector, template_encoder
from app.services.matcher import match_against_set, is_match

router = APIRouter()


@router.post("/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest, db: Session = Depends(get_db)):
    """
    Verify a user's identity (1:1 match).

    1. Load the most recent enrollment for the given user_id.
    2. Process the incoming finger images (quality + liveness + template).
    3. Match probe templates against stored templates.
    4. Return match result + confidence score.
    """
    # ── Load stored templates ─────────────────────────────────────────────────
    user = db.get(User, request.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User '{request.user_id}' not found")

    latest_enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == request.user_id)
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )
    if latest_enrollment is None:
        raise HTTPException(status_code=404, detail=f"No enrollment found for user '{request.user_id}'")

    stored: dict[str, str] = {
        ft.finger_id: ft.template
        for ft in latest_enrollment.fingers
    }

    if not stored:
        raise HTTPException(status_code=404, detail="Enrollment has no stored templates")

    # ── Process probe images ──────────────────────────────────────────────────
    probe: Dict[str, str] = {}
    processing_errors: List[str] = []

    for finger in request.fingers:
        fid = finger.finger_id.upper()

        try:
            bgr      = image_processor.base64_to_mat(finger.image_base64)
            gray     = image_processor.to_gray(bgr)
            q        = quality_analyzer.analyze(gray)
            liveness = liveness_detector.evaluate(gray)

            if not q.passed:
                processing_errors.append(f"{fid}: quality too low ({q.score:.1f})")
                continue

            if not liveness.passed:
                processing_errors.append(f"{fid}: liveness failed — {liveness.reason}")
                continue

            skeleton = image_processor.enhance(bgr)
            template = template_encoder.encode(skeleton, quality_score=q.score)

            if template is None:
                processing_errors.append(f"{fid}: insufficient ridge detail")
                continue

            probe[fid] = template

        except Exception as e:
            processing_errors.append(f"{fid}: processing error — {str(e)}")

    if not probe:
        return VerifyResponse(
            transaction_id=request.transaction_id,
            user_id=request.user_id,
            match=False,
            confidence=0.0,
            message=f"No probe templates generated. Issues: {'; '.join(processing_errors)}"
        )

    # ── Match ─────────────────────────────────────────────────────────────────
    confidence = match_against_set(probe, stored)
    matched, _ = is_match(
        next(iter(probe.values())),
        next(iter(stored.values()))
    ) if len(probe) == 1 and len(stored) == 1 else (confidence >= 0.35, confidence)

    # Use multi-finger average when available
    matched = confidence >= 0.35

    message = "Identity verified" if matched else "Identity not verified"
    if processing_errors:
        message += f" (note: {len(processing_errors)} finger(s) skipped)"

    return VerifyResponse(
        transaction_id=request.transaction_id,
        user_id=request.user_id,
        match=matched,
        confidence=round(confidence, 4),
        message=message
    )
