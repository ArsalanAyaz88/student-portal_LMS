# File: app/schemas/enrollment.py
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

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

class EnrollmentStatus(BaseModel):
    status: str
    message: str
    expiration_date: Optional[datetime]
    days_remaining: Optional[int]
    is_expired: bool
    is_accessible: bool

    class Config:
        from_attributes = True