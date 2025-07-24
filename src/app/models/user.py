# File: app/models/user.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.models.assignment import AssignmentSubmission
    from src.app.models.enrollment import Enrollment, EnrollmentApplication
    from src.app.models.oauth import OAuthAccount
    from src.app.models.profile import Profile
    from src.app.models.video_progress import VideoProgress
    from src.app.models.quiz import QuizSubmission

class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(index=True, unique=True, nullable=False)
    hashed_password: Optional[str] = None  # Optional for OAuth users
    role: str = Field(default="student", nullable=False)
    is_active: bool = Field(default=True)
    suspended_at: Optional[str] = None
    suspend_reason: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # Relationships
    oauth_accounts: List["OAuthAccount"] = Relationship(back_populates="user")
    assignment_submissions: List["AssignmentSubmission"] = Relationship(back_populates="student")
    video_progress: List["VideoProgress"] = Relationship(back_populates="user")
    quiz_submissions: List["QuizSubmission"] = Relationship(back_populates="student")
    enrollment_applications: List["EnrollmentApplication"] = Relationship(back_populates="user", sa_relationship_kwargs={"foreign_keys": "[EnrollmentApplication.user_id]"})
    enrollments: List["Enrollment"] = Relationship(back_populates="user", sa_relationship_kwargs={"foreign_keys": "[Enrollment.user_id]"})

