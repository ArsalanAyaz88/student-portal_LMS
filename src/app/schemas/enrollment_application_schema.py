import uuid
from pydantic import BaseModel
from typing import Optional
from src.app.models.enrollment_application import ApplicationStatus

# Base schema with common application fields
class EnrollmentApplicationBase(BaseModel):
    first_name: str
    last_name: str
    qualification: str
    ultrasound_experience: Optional[str] = None
    contact_number: str

# Schema for creating a new application
class EnrollmentApplicationCreate(EnrollmentApplicationBase):
    course_id: uuid.UUID

# Schema for updating an application's status
class EnrollmentApplicationUpdate(BaseModel):
    status: ApplicationStatus
    rejection_reason: Optional[str] = None

# Schema for reading a full application record
class EnrollmentApplicationRead(EnrollmentApplicationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    status: ApplicationStatus
    qualification_certificate_url: str

    class Config:
        from_attributes = True
