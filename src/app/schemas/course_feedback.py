from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class CourseFeedbackCreate(BaseModel):
    feedback: str
    improvement_suggestions: Optional[str] = None

class CourseFeedbackRead(BaseModel):
    id: UUID
    user_id: UUID
    course_id: UUID
    feedback: str
    improvement_suggestions: Optional[str] = None
    submitted_at: datetime

    class Config:
        orm_mode = True
