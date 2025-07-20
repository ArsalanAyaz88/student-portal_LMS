# File: app/models/video.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.app.models.course import Course
    from src.app.models.video_progress import VideoProgress
    from src.app.models.quiz import Quiz

class Video(SQLModel, table=True):
    __tablename__ = 'video'
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: uuid.UUID = Field(foreign_key="course.id")
    
    cloudinary_url: str = Field(index=True)
    public_id: Optional[str] = Field(default=None, index=True) # Cloudinary public ID
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[float] = None  # Duration in seconds
    order: int = Field(default=0)  # Order of the video in the course
    is_preview: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    course: "Course" = Relationship(back_populates="videos", sa_relationship_kwargs={'foreign_keys': '[Video.course_id]'})
    progress: List["VideoProgress"] = Relationship(back_populates="video", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    quiz_id: Optional[uuid.UUID] = Field(default=None, foreign_key="quiz.id")
    quiz: Optional["Quiz"] = Relationship(back_populates="videos")
