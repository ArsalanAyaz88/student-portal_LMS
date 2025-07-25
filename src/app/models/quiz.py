# quiz.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from src.app.utils.time import get_pakistan_time

if TYPE_CHECKING:
    from src.app.models.course import Course
    from src.app.models.quiz_audit_log import QuizAuditLog
    
    from src.app.models.video import Video

class Quiz(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    course_id: uuid.UUID = Field(foreign_key="course.id")
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

    questions: List["Question"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    submissions: List["QuizSubmission"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    audit_logs: List["QuizAuditLog"] = Relationship(back_populates="quiz", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    video_id: uuid.UUID = Field(foreign_key="video.id", unique=True)
    video: "Video" = Relationship(back_populates="quiz")

    # The relationship to Course might be redundant if Quiz is always tied to a Video,
    # which is already tied to a Course. For now, we leave it.
    course: "Course" = Relationship(back_populates="quizzes")

class Question(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quiz.id")
    text: str
    is_multiple_choice: bool = Field(default=False)

    quiz: "Quiz" = Relationship(back_populates="questions")
    options: List["Option"] = Relationship(back_populates="question", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class Option(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="question.id")
    text: str
    is_correct: bool = Field(default=False)

    question: "Question" = Relationship(back_populates="options")

class QuizSubmission(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quiz.id")
    student_id: uuid.UUID = Field(foreign_key="user.id")
    submitted_at: datetime = Field(default_factory=get_pakistan_time)
    score: Optional[float] = None
    is_graded: bool = Field(default=False)

    quiz: "Quiz" = Relationship(back_populates="submissions")
    user: "User" = Relationship(back_populates="quiz_submissions")
    answers: List["Answer"] = Relationship(back_populates="submission", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class Answer(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    submission_id: uuid.UUID = Field(foreign_key="quizsubmission.id")
    question_id: uuid.UUID = Field(foreign_key="question.id")
    selected_option_id: Optional[uuid.UUID] = Field(default=None, foreign_key="option.id")
    text_answer: Optional[str] = None

    submission: "QuizSubmission" = Relationship(back_populates="answers")
    selected_option: Optional["Option"] = Relationship()
