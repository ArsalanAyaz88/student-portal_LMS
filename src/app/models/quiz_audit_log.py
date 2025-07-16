# File: application/src/app/models/quiz_audit_log.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING: 
    from src.app.models.quiz import Quiz

class QuizAuditLog(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="user.id")
    quiz_id: uuid.UUID = Field(foreign_key="quiz.id")
    action: str  # e.g., "submit", "view_result"
    timestamp: datetime = Field(default_factory=get_pakistan_time)
    details: Optional[str] = None

    quiz: "src.app.models.quiz.Quiz" = Relationship(back_populates="audit_logs")
