# File: app/models/video.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import Optional, TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.app.models.course import Course
    from src.app.models.video_progress import VideoProgress

class Video(SQLModel, table=True):
    __tablename__ = 'video'
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: uuid.UUID = Field(foreign_key="course.id")
    
    cloudinary_url: str = Field(index=True)
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None  # Duration in seconds
    is_preview: bool = Field(default=False)

    course: "Course" = Relationship(back_populates="videos", sa_relationship_kwargs={'foreign_keys': '[Video.course_id]'})
    progress: List["VideoProgress"] = Relationship(back_populates="video", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
