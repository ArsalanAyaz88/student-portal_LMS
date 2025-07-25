# File: app/models/enrollment.py
from __future__ import annotations
import uuid
import enum
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlmodel import SQLModel, Field, Relationship



# --- Enums ---

class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# --- Models ---




class EnrollmentApplication(SQLModel, table=True):
    __tablename__ = "enrollment_applications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str
    last_name: str
    qualification: str
    qualification_certificate_url: str
    ultrasound_experience: Optional[str] = None
    contact_number: str
    
    status: ApplicationStatus = Field(
        sa_column=SQLAlchemyEnum(ApplicationStatus, name="application_status_enum"),
        default=ApplicationStatus.PENDING
    )

    user_id: uuid.UUID = Field(foreign_key="user.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")

    # --- Relationships ---
    user: "User" = Relationship(back_populates="enrollment_applications")
    course: "Course" = Relationship(back_populates="enrollment_applications")



    



class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")
    status: str = Field(default="pending")
    enroll_date: datetime = Field(default_factory=datetime.utcnow)
    expiration_date: Optional[datetime] = None
    is_accessible: bool = Field(default=False)

    # --- Relationships ---
    user: "User" = Relationship(back_populates="enrollments")
    course: "Course" = Relationship(back_populates="enrollments")
