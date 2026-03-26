"""
Session/Transaction Management API
GET /api/session  →  generates a unique transactionId for every capture attempt.
Required by the Flutter SDK for audit trail and replay-attack prevention.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter()


@router.get("/session")
def create_session():
    """
    Generate a unique transaction ID for a new capture session.

    The Flutter SDK calls this before starting any capture.
    The returned transactionId must be passed back in every subsequent
    API call (capture, enroll, verify, audit) so all events can be
    grouped and audited together.
    """
    return {
        "transaction_id": str(uuid.uuid4()),
        "issued_at":      datetime.now(timezone.utc).isoformat(),
        "expires_in":     300,          # client should complete capture within 5 min
    }
