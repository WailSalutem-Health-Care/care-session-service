"""Feedback database model"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.postgres import Base


class Feedback(Base):
    """Patient feedback for completed care sessions"""
    __tablename__ = "feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    care_session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    caregiver_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-3: 1=Dissatisfied, 2=Neutral, 3=Satisfied
    patient_feedback = Column(Text, nullable=True)  # Optional text feedback from patient
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
