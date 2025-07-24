# File: app/schemas/enrollment.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, TYPE_CHECKING

from src.app.models.enrollment import ApplicationStatus

if TYPE_CHECKING:
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
    days_remaining: Optional[int]
    is_expired: bool
    is_accessible: bool
    last_access_date: Optional[datetime]

    class Config:
        from_attributes = True

class EnrollmentStatusResponse(BaseModel):
    status: str

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
    user_id: uuid.UUID # Keep this for direct access
    course_id: uuid.UUID # Keep this for direct access
    user: "UserRead"
    course: "CourseRead"
    status: ApplicationStatus
    qualification_certificate_url: str

    class Config:
        from_attributes = True

# --- Payment Proof Schemas ---

class PaymentProofCreate(BaseModel):
    application_id: uuid.UUID

class PaymentProofRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    proof_url: str
    uploaded_at: datetime
    is_verified: bool

    class Config:
        from_attributes = True

# Manually update forward references to resolve circular dependencies
from .user import UserRead
from .course import CourseRead

EnrollmentApplicationRead.model_rebuild()
