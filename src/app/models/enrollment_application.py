import uuid
from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field, Relationship, Column
import enum
from sqlalchemy import Enum as SQLAlchemyEnum

if TYPE_CHECKING:
    from .user import User
    from .course import Course
    from .payment_proof import PaymentProof

class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    VERIFIED = "VERIFIED"

class EnrollmentApplication(SQLModel, table=True):
    __tablename__ = "enrollment_applications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING, sa_column=Column(SQLAlchemyEnum(ApplicationStatus)))
    payment_status: PaymentStatus = Field(default=PaymentStatus.UNPAID, sa_column=Column(SQLAlchemyEnum(PaymentStatus)))
    qualification: Optional[str] = None
    ultrasound_experience: Optional[str] = None
    contact_number: Optional[str] = None
    qualification_certificate_url: Optional[str] = None

    user: "User" = Relationship(back_populates="enrollment_applications")
    course: "Course" = Relationship(back_populates="enrollment_applications")
    payment_proof: Optional["PaymentProof"] = Relationship(back_populates="enrollment_application")