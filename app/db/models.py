from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Text, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from app.db.postgres import Base

class CareSession(Base):
    """
    Care session tracking for caregiver check-ins/check-outs.
    Owned by care-session-service.
    """
    __tablename__ = "care_sessions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    caregiver_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    check_in_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    check_out_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress", nullable=False, index=True)  # in_progress | completed | cancelled
    caregiver_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class NFCTag(Base):
    """
    NFC tags table - owned by another service.
    Defined here for read-only queries (validation during check-in).
    """
    __tablename__ = "nfc_tags"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    tag_id = Column(String(255), unique=True, nullable=False, index=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    issued_at = Column(DateTime, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Patient(Base):
    """
    Patients table - owned by another service.
    Defined here for read-only queries (getting patient details).
    """
    __tablename__ = "patients"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address = Column(Text, nullable=True)
    medical_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)


class User(Base):
    """
    Caregivers table - owned by another service.
    Local cache for reporting and validation.
    """
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
