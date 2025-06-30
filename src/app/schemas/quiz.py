# d:\course_lms\student-portal_LMS\src\app\schemas\quiz.py
from pydantic import BaseModel, Field
import uuid
from typing import List, Optional
from datetime import datetime

# --- Option Schemas ---

class OptionBase(BaseModel):
    text: str
    is_correct: bool

class OptionCreate(OptionBase):
    pass

class OptionRead(OptionBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

# --- Question Schemas ---

class QuestionBase(BaseModel):
    text: str
    question_type: str = "multiple_choice"
    points: int = 1

class QuestionCreate(QuestionBase):
    options: List[OptionCreate]

class QuestionRead(QuestionBase):
    id: uuid.UUID
    options: List[OptionRead]

    class Config:
        from_attributes = True

# --- Quiz Schemas ---

class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    published: bool = False

class QuizCreate(QuizBase):
    pass # No extra fields needed for creation initially

class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    published: Optional[bool] = None

class QuizRead(QuizBase):
    id: uuid.UUID
    course_id: uuid.UUID

    class Config:
        from_attributes = True

class QuizReadWithDetails(QuizRead):
    questions: List[QuestionRead] = []

# --- Submission and Grading Schemas ---

class StudentRead(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str

    class Config:
        from_attributes = True


class AnswerRead(BaseModel):
    question_id: uuid.UUID
    selected_option_id: Optional[uuid.UUID] = None
    text_answer: Optional[str] = None

    class Config:
        from_attributes = True

class QuizSubmissionRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime
    score: Optional[float] = None
    is_graded: bool
    feedback: Optional[str] = None

    class Config:
        from_attributes = True

class QuizSubmissionReadWithStudent(QuizSubmissionRead):
    student: StudentRead

class QuizSubmissionReadWithDetails(QuizSubmissionReadWithStudent):
    answers: List[AnswerRead]


class GradeSubmissionRequest(BaseModel):
    score: float
    feedback: Optional[str] = None


class GradingViewSchema(BaseModel):
    submission: QuizSubmissionReadWithDetails
    quiz: QuizReadWithDetails

# Schemas for legacy admin controller - to be deprecated
class QuizSubmissionStatus(BaseModel):
    submission_id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime
    is_on_time: bool

QuizResult = QuizSubmissionRead  # Alias for compatibility

