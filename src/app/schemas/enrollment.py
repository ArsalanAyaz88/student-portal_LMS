# File: app/schemas/enrollment.py
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING

# Import ApplicationStatus from the correct model file
from src.app.models.enrollment import ApplicationStatus

from .user import UserRead
from .course import CourseRead

# --- Enrollment Schemas ---

class EnrollmentCreate(BaseModel):
    course_id: uuid.UUID

class EnrollmentRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    status: str
    enroll_date: Optional[datetime]
    expiration_date: Optional[datetime]
    is_accessible: bool

    class Config:
        from_attributes = True

class EnrollmentStatusResponse(BaseModel):
    status: str
    application_id: Optional[uuid.UUID] = None

# --- Enrollment Application Schemas ---

class EnrollmentApplicationBase(BaseModel):
    first_name: str
    last_name: str
    qualification: str
    ultrasound_experience: Optional[str] = None
    contact_number: str

class EnrollmentApplicationCreate(EnrollmentApplicationBase):
    course_id: uuid.UUID
    qualification_certificate_url: str

class EnrollmentApplicationUpdate(BaseModel):
    status: ApplicationStatus
    rejection_reason: Optional[str] = None

class EnrollmentApplicationRead(EnrollmentApplicationBase):
    id: uuid.UUID
    user: "UserRead"
    course: "CourseRead"
    status: ApplicationStatus
    qualification_certificate_url: str

    class Config:
        from_attributes = True

# --- Payment Proof Schemas ---

class PaymentProofCreate(BaseModel):
    application_id: uuid.UUID
    transaction_id: str
    bank_account_id: uuid.UUID
    proof_url: str

class PaymentProofRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    transaction_id: str
    bank_account_id: uuid.UUID
    proof_url: str
    uploaded_at: datetime
    is_verified: bool

    class Config:
        from_attributes = True

# FIX: Rebuild the model to resolve forward references like 'User' and 'Course'
# This is the key to fixing the SQLAlchemy mapper error without causing circular imports.
EnrollmentApplicationRead.model_rebuild()