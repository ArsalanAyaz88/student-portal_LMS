from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time

class CourseFeedback(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")
    feedback: str
    improvement_suggestions: Optional[str] = None
    submitted_at: datetime = Field(default_factory=get_pakistan_time)
