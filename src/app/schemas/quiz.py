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

class QuestionCreate(QuestionBase):
    options: List[OptionCreate]

class QuestionUpdate(QuestionCreate):
    pass

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

class QuizCreate(QuizBase):
    course_id: uuid.UUID
    questions: List[QuestionCreate] = []

class QuizCreateForVideo(QuizBase):
    questions: List[QuestionCreate] = []

class QuizCreateWithQuestions(QuizCreate):
    pass

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

    class Config:
        from_attributes = True

class QuizSubmissionReadWithStudent(QuizSubmissionRead):
    student: StudentRead

class QuizSubmissionReadWithDetails(QuizSubmissionReadWithStudent):
    answers: List[AnswerRead]


class GradeSubmissionRequest(BaseModel):
    score: float





class GradingViewSchema(BaseModel):
    submission: QuizSubmissionReadWithDetails
    quiz: QuizReadWithDetails

# Schemas for legacy admin controller - to be deprecated
class QuizSubmissionStatus(BaseModel):
    submission_id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime
    is_on_time: bool

# Schemas for quiz results returned to students
class ResultAnswer(BaseModel):
    question_id: uuid.UUID
    question_text: str
    selected_option_id: uuid.UUID
    selected_option_text: str
    correct_option_id: uuid.UUID
    correct_option_text: str
    is_correct: bool

class QuizResult(BaseModel):
    submission_id: uuid.UUID
    quiz_title: str
    score: float
    total_questions: int
    answers: List[ResultAnswer]

class AnswerCreate(BaseModel):
    question_id: uuid.UUID
    selected_option_id: Optional[uuid.UUID] = None

class QuizSubmissionCreate(BaseModel):
    answers: List[AnswerCreate]


class QuizListRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    is_submitted: bool = False
    score: Optional[float] = None
    submission_id: Optional[uuid.UUID] = None
    total_questions: int = 0

    class Config:
        from_attributes = True


# --- Aliases for router responses ---
QuizDetailRead = QuizReadWithDetails

