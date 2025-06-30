# quiz.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from src.app.utils.time import get_pakistan_time

if TYPE_CHECKING:
    from src.app.models.course import Course
    from src.app.models.quiz_audit_log import QuizAuditLog

class Quiz(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: uuid.UUID = Field(foreign_key="course.id")
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

    questions: List["src.app.models.quiz.Question"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    submissions: List["src.app.models.quiz.QuizSubmission"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    audit_logs: List["src.app.models.quiz_audit_log.QuizAuditLog"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    course: "Course" = Relationship(back_populates="quizzes")

class Question(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quiz.id")
    text: str
    points: int = Field(default=1) # Points for a correct answer

    quiz: Quiz = Relationship(back_populates="questions")
    options: List["src.app.models.quiz.Option"] = Relationship(back_populates="question", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class Option(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="question.id")
    text: str
    is_correct: bool = Field(default=False)

    question: Question = Relationship(back_populates="options")

class QuizSubmission(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quiz.id")
    student_id: uuid.UUID = Field(foreign_key="user.id")
    submitted_at: datetime = Field(default_factory=get_pakistan_time)
    score: Optional[float] = None
    is_graded: bool = Field(default=False)
    feedback: Optional[str] = None # Feedback from the grader

    quiz: "src.app.models.quiz.Quiz" = Relationship(back_populates="submissions")

    answers: List["src.app.models.quiz.Answer"] = Relationship(back_populates="submission", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class Answer(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    submission_id: uuid.UUID = Field(foreign_key="quizsubmission.id")
    question_id: uuid.UUID = Field(foreign_key="question.id")
    selected_option_id: Optional[uuid.UUID] = None
    text_answer: Optional[str] = None

    submission: QuizSubmission = Relationship(back_populates="answers")
