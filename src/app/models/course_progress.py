from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import Column, Boolean, Float
from datetime import datetime
from src.app.utils.time import get_pakistan_time

if TYPE_CHECKING:
    from src.app.models.course import Course
    from src.app.models.user import User
    from src.app.models.video import Video 

class CourseProgress(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    course_id: uuid.UUID = Field(foreign_key="course.id", nullable=False)
    completed: bool = Field(default=False)
    progress_percentage: float = Field(default=0.0)
    last_accessed_video_id: Optional[uuid.UUID] = Field(foreign_key="video.id", nullable=True)
    completed_at: Optional[datetime] = Field(default=None)
 
    course: "src.app.models.course.Course" = Relationship(back_populates="progress")