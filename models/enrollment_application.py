import uuid
from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field, Relationship
import enum
from sqlalchemy import Enum as SQLAlchemyEnum

if TYPE_CHECKING:
    from src.app.models.user import User
    from src.app.models.course import Course

class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

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

    user: "User" = Relationship(back_populates="enrollment_applications")
    course: "Course" = Relationship(back_populates="enrollment_applications")