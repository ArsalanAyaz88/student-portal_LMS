import uuid
from pydantic import BaseModel
from typing import Optional
from src.app.models.enrollment_application import ApplicationStatus

# Schema for the data a student submits when applying
class EnrollmentApplicationCreate(BaseModel):
    first_name: str
    last_name: str
    qualification: str
    ultrasound_experience: Optional[str] = None
    contact_number: str

# Schema for reading a full application record (e.g., for an admin)
class EnrollmentApplicationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    first_name: str
    last_name: str
    qualification: str
    qualification_certificate_url: str
    ultrasound_experience: Optional[str] = None
    contact_number: str
    status: ApplicationStatus

    class Config:
        orm_mode = True

# Schema for the admin to see a list of applications
class EnrollmentApplicationAdminRead(BaseModel):
    id: uuid.UUID
    course_title: str # We'll join to get this
    student_email: str # We'll join to get this
    status: ApplicationStatus

    class Config:
        orm_mode = True

# Schema for updating the status
class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    message: Optional[str] = None # Optional message for rejection email
