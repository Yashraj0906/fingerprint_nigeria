import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User, Enrollment, FingerTemplate
from app.models.schemas import EnrollRequest, EnrollResponse

router = APIRouter()


@router.post("/enroll", response_model=EnrollResponse)
def enroll(request: EnrollRequest, db: Session = Depends(get_db)):
    """
    Enroll a user's fingerprint templates.

    - Creates the user record if they don't exist yet.
    - Creates a new Enrollment linked to the user.
    - Stores one FingerTemplate row per finger.

    The Flutter app calls this when the user taps "Confirm & Submit"
    and all fingers have been successfully captured.
    """
    if not request.fingers:
        raise HTTPException(status_code=400, detail="No finger templates provided")

    # ── Upsert user ───────────────────────────────────────────────────────────
    user = db.get(User, request.user_id)
    if user is None:
        user = User(id=request.user_id)
        db.add(user)

    # ── Create enrollment ─────────────────────────────────────────────────────
    enrollment = Enrollment(
        id=str(uuid.uuid4()),
        user_id=request.user_id,
        transaction_id=request.transaction_id
    )
    db.add(enrollment)

    # ── Store templates ───────────────────────────────────────────────────────
    enrolled_fingers: list[str] = []
    for f in request.fingers:
        ft = FingerTemplate(
            id=str(uuid.uuid4()),
            enrollment_id=enrollment.id,
            finger_id=f.finger_id.upper(),
            template=f.template,
            quality_score=f.quality_score
        )
        db.add(ft)
        enrolled_fingers.append(f.finger_id.upper())

    db.commit()

    return EnrollResponse(
        enrollment_id=enrollment.id,
        user_id=request.user_id,
        status="enrolled",
        fingers_enrolled=enrolled_fingers
    )
