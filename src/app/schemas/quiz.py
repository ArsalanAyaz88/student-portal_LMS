# File: application/src/app/schemas/quiz.py

from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# ─── Admin / Input Schemas ─────────────────────────────────────

class OptionCreate(BaseModel):
    text: str
    is_correct: bool

class QuestionCreate(BaseModel):
    text: str
    is_multiple_choice: bool
    options: List[OptionCreate]

class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class QuizCreate(BaseModel):
    title: str
    description: Optional[str]
    questions: List[QuestionCreate]

# ─── Shared Base for Reads ──────────────────────────────────────

class QuizBase(BaseModel):
    id: UUID
    course_id: UUID
    title: str
    description: Optional[str]

    class Config:
        orm_mode = True
        from_attributes = True

# ─── Student‐Facing: List vs Detail ────────────────────────────

class QuizListRead(QuizBase):
    """Lightweight list view: no questions."""
    pass

class OptionRead(BaseModel):
    id: UUID
    text: str

    class Config:
        orm_mode = True
        from_attributes = True

class QuestionRead(BaseModel):
    id: UUID
    text: str
    is_multiple_choice: bool
    options: List[OptionRead]

    class Config:
        orm_mode = True
        from_attributes = True

class QuizDetailRead(QuizBase):
    """Full detail view: includes questions + options."""
    questions: List[QuestionRead]

# ─── Admin‐Facing: alias read schema ───────────────────────────

class QuizRead(QuizDetailRead):
    """Alias for admin controllers that expect `QuizRead`."""
    pass

# ─── Submission / Result Schemas ───────────────────────────────

class AnswerCreate(BaseModel):
    question_id: UUID
    selected_option_id: Optional[UUID]

class QuizSubmissionCreate(BaseModel):
    answers: List[AnswerCreate]

class QuizResultDetail(BaseModel):
    question_id: UUID
    correct: bool


class QuizSubmissionStatus(BaseModel):
    submission_id: UUID
    student_id: UUID
    submitted_at: datetime
    is_on_time: bool

    class Config:
        orm_mode = True
        from_attributes = True

class QuizResult(BaseModel):
    submission_id: UUID
    score: float
    total: int
    details: List[QuizResultDetail]

    class Config:
        orm_mode = True
        from_attributes = True
