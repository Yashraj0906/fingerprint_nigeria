"""
Audit & Operational Logs API
POST /api/audit/log  →  records security events, errors, and performance data.

The Flutter SDK (and backend itself) posts here for:
- Liveness failures (blocked spoofing attempts)
- Capture errors (blur, low quality, decode failures)
- Successful enrollments and verifications
- Device info for forensic tracing
"""

import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import AuditLog

router = APIRouter()


class AuditLogRequest(BaseModel):
    transaction_id: str
    event_type:     str                     # CAPTURE | ENROLL | VERIFY | LIVENESS_FAIL | ERROR
    status:         str                     # success | failed
    user_id:        Optional[str] = None
    finger_id:      Optional[str] = None
    error_code:     Optional[str] = None
    quality_score:  Optional[float] = None
    device_info:    Optional[Dict[str, Any]] = None   # SDK version, OS, device model


class AuditLogResponse(BaseModel):
    log_id:     str
    recorded_at: str


@router.post("/audit/log", response_model=AuditLogResponse)
def record_audit_event(request: AuditLogRequest, db: Session = Depends(get_db)):
    """
    Record a security or operational event.

    Called by:
    - Flutter SDK: after each capture attempt (liveness pass/fail, quality score)
    - Backend: automatically on enroll/verify (internal use)

    Stored data enables:
    - Security auditing (who tried what, when, from which device)
    - Performance monitoring (average quality scores, failure rates)
    - Compliance reporting
    """
    log = AuditLog(
        id             = str(uuid.uuid4()),
        transaction_id = request.transaction_id,
        event_type     = request.event_type.upper(),
        user_id        = request.user_id,
        finger_id      = request.finger_id,
        status         = request.status,
        error_code     = request.error_code,
        quality_score  = request.quality_score,
        device_info    = json.dumps(request.device_info) if request.device_info else None,
        created_at     = datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()

    return AuditLogResponse(
        log_id      = log.id,
        recorded_at = log.created_at.isoformat(),
    )


@router.get("/audit/logs")
def get_audit_logs(
    transaction_id: Optional[str] = None,
    event_type:     Optional[str] = None,
    limit:          int            = 50,
    db:             Session        = Depends(get_db),
):
    """
    Retrieve audit logs. Filter by transaction_id or event_type.
    Used for monitoring dashboard and compliance review.
    """
    query = db.query(AuditLog)
    if transaction_id:
        query = query.filter(AuditLog.transaction_id == transaction_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type.upper())

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [
        {
            "log_id":         l.id,
            "transaction_id": l.transaction_id,
            "event_type":     l.event_type,
            "user_id":        l.user_id,
            "finger_id":      l.finger_id,
            "status":         l.status,
            "error_code":     l.error_code,
            "quality_score":  l.quality_score,
            "device_info":    json.loads(l.device_info) if l.device_info else None,
            "created_at":     l.created_at.isoformat(),
        }
        for l in logs
    ]
