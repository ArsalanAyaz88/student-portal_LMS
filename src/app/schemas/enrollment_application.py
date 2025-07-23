# File: src/app/schemas/enrollment_application.py
from pydantic import BaseModel, Field
import uuid
from typing import Optional
from src.app.models.enrollment_application import ApplicationStatus

class EnrollmentApplicationBase(BaseModel):
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    qualification: str = Field(..., example="MBBS")
    qualification_certificate_url: str = Field(..., example="https://example.com/cert.pdf")
    ultrasound_experience: Optional[str] = Field(default=None, example="2 years experience in a clinical setting.")
    contact_number: str = Field(..., example="+1234567890")

class EnrollmentApplicationCreate(EnrollmentApplicationBase):
    course_id: uuid.UUID

class EnrollmentApplicationRead(EnrollmentApplicationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    status: ApplicationStatus

    class Config:
        from_attributes = True
