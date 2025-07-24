# File: app/models/enrollment.py
from __future__ import annotations
import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from src.app.models.user import User
    from src.app.models.course import Course
    from src.app.models.bank_account import BankAccount
    from src.app.models.payment import PaymentProof

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

    user: "User" = Relationship()
    course: "Course" = Relationship(back_populates="enrollment_applications")
    
    # Relationship to payment proofs
    payment_proofs: List["PaymentProof"] = Relationship(back_populates="application", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")
    status: str = Field(default="pending")
    enroll_date: datetime = Field(default_factory=datetime.utcnow)
    expiration_date: Optional[datetime] = None
    is_accessible: bool = Field(default=False)

    user: "User" = Relationship(back_populates="enrollments")
    course: "Course" = Relationship(back_populates="enrollments")