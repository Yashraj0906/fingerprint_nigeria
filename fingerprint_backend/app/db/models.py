from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True)   # caller-supplied user ID
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id             = Column(String, primary_key=True)   # enrollment UUID
    user_id        = Column(String, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(String, nullable=False)
    enrolled_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user    = relationship("User", back_populates="enrollments")
    fingers = relationship("FingerTemplate", back_populates="enrollment", cascade="all, delete-orphan")


class FingerTemplate(Base):
    __tablename__ = "finger_templates"

    id            = Column(String, primary_key=True)   # UUID
    enrollment_id = Column(String, ForeignKey("enrollments.id"), nullable=False)
    finger_id     = Column(String, nullable=False)     # e.g. RIGHT_INDEX
    template      = Column(String, nullable=False)     # base64 ISO 19794-2
    quality_score = Column(Float,  nullable=False)

    enrollment = relationship("Enrollment", back_populates="fingers")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id             = Column(String,   primary_key=True)
    transaction_id = Column(String,   nullable=False, index=True)
    event_type     = Column(String,   nullable=False)   # CAPTURE | ENROLL | VERIFY | LIVENESS_FAIL | ERROR
    user_id        = Column(String,   nullable=True)
    finger_id      = Column(String,   nullable=True)
    status         = Column(String,   nullable=False)   # success | failed
    error_code     = Column(String,   nullable=True)
    device_info    = Column(Text,     nullable=True)    # JSON string from SDK
    quality_score  = Column(Float,    nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
