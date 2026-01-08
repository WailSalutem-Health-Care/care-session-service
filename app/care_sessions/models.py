from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.postgres import Base


class CareSession(Base):
    """Care session tracking for caregiver check-ins/check-outs"""
    __tablename__ = "care_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(String(50), unique=True, nullable=False, index=True, default=lambda: str(uuid4()))
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    caregiver_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    check_in_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    check_out_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress", nullable=False, index=True)
    caregiver_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
