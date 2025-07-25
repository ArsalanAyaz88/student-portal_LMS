from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Column, Text, ForeignKey
from datetime import datetime
from src.app.utils.time import get_pakistan_time

if TYPE_CHECKING:
    from src.app.models.video import Video
    from src.app.models.enrollment import Enrollment
    from src.app.models.course_progress import CourseProgress
    from src.app.models.assignment import Assignment
    from src.app.models.quiz import Quiz
    from src.app.models.enrollment import EnrollmentApplication

class Course(SQLModel, table=True):
    __tablename__ = 'course'
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: str
    price: float = Field(default=0.0)
    thumbnail_url: Optional[str] = None
    preview_video_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column(ForeignKey("video.id", ondelete="SET NULL")))
    difficulty_level: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=get_pakistan_time)
    updated_at: datetime = Field(default_factory=get_pakistan_time)
    outcomes: str = Field(default="", sa_column=Column(Text))
    prerequisites: str = Field(default="", sa_column=Column(Text))
    curriculum: str = Field(default="", sa_column=Column(Text))
    status: str = Field(default="active")

    # Relationships
    preview_video: Optional["Video"] = Relationship(sa_relationship_kwargs={"primaryjoin": "Course.preview_video_id == Video.id", "foreign_keys": "[Course.preview_video_id]", "uselist": False, "post_update": True})
    videos: List["Video"] = Relationship(back_populates="course", sa_relationship_kwargs={"foreign_keys": "[Video.course_id]", "cascade": "all, delete-orphan"})
    progress: List["CourseProgress"] = Relationship(back_populates="course", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    assignments: List["Assignment"] = Relationship(back_populates="course", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    enrollments: List["Enrollment"] = Relationship(back_populates="course")
    enrollment_applications: List["EnrollmentApplication"] = Relationship(back_populates="course", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    quizzes: List["Quiz"] = Relationship(back_populates="course", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
