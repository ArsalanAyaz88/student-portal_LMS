from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from typing import List
import uuid
from typing import List

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.quiz import Quiz, Question, Option
from src.app.schemas.quiz import (
    QuizCreate, QuizRead, QuizUpdate, 
    QuestionCreate, QuestionRead, QuestionUpdate, 
    QuizSubmissionCreate, QuizSubmissionRead, GradeSubmissionRequest,
    QuizReadWithDetails, QuizSubmissionReadWithStudent, GradingViewSchema
)
from src.app.utils.dependencies import get_current_admin_user

# --- Router Definitions ---
# Using distinct routers for each resource type for a clean, RESTful API design.
quiz_router = APIRouter(prefix="/quizzes", tags=["Admin Quizzes"])
question_router = APIRouter(prefix="/questions", tags=["Admin Questions"])
submission_router = APIRouter(prefix="/submissions", tags=["Admin Submissions"])


# --- Quiz Management Endpoints ---

@quiz_router.post("/course/{course_id}", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def create_quiz_for_course(
    course_id: uuid.UUID,
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Create a new quiz for a specific course."""
    if not db.get(Course, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    new_quiz = Quiz.from_orm(quiz_data, update={'course_id': course_id})
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    return new_quiz

@quiz_router.get("/{quiz_id}", response_model=QuizReadWithDetails)
def get_quiz_details(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Get detailed information about a specific quiz, including its questions and options."""
    statement = select(Quiz).where(Quiz.id == quiz_id).options(joinedload(Quiz.questions).joinedload(Question.options))
    quiz = db.exec(statement).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return quiz

@quiz_router.put("/{quiz_id}", response_model=QuizRead)
def update_quiz(
    quiz_id: uuid.UUID,
    quiz_data: QuizUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Update a quiz's details."""
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    for key, value in quiz_data.dict(exclude_unset=True).items():
        setattr(quiz, key, value)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz

@quiz_router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Delete a quiz."""
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    db.delete(quiz)
    db.commit()
    return

@quiz_router.post("/{quiz_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def add_question_to_quiz(
    quiz_id: uuid.UUID,
    question_data: QuestionCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Add a new question to a specific quiz."""
    if not db.get(Quiz, quiz_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    new_question = Question(text=question_data.text, quiz_id=quiz_id)
    new_question.options = [
        Option(text=opt.text, is_correct=opt.is_correct) 
        for opt in question_data.options
    ]

    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return new_question


# --- Question Management Endpoints ---

@question_router.put("/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: uuid.UUID,
    question_data: QuestionUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Update a specific question's text and options, avoiding the collection replacement bug."""
    db_question = db.get(Question, question_id)
    if not db_question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    # Update the question's text
    db_question.text = question_data.text

    # Manually delete old options to bypass the library bug
    for option in db_question.options:
        db.delete(option)
    db.flush()

    # Manually create and add new options
    for option_data in question_data.options:
        new_option = Option(text=option_data.text, is_correct=option_data.is_correct, question_id=question_id)
        db.add(new_option)

    db.commit()
    db.refresh(db_question)
    return db_question

@question_router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Delete a question."""
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    db.delete(question)
    db.commit()
    return


# --- Submission and Grading Endpoints ---

@submission_router.get("/quiz/{quiz_id}", response_model=List[QuizSubmissionReadWithStudent])
def get_quiz_submissions(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Get all submissions for a specific quiz."""
    statement = select(QuizSubmission).where(QuizSubmission.quiz_id == quiz_id).options(joinedload(QuizSubmission.student)).order_by(QuizSubmission.submitted_at.desc())
    return db.exec(statement).all()

@submission_router.get("/{submission_id}/grading-view", response_model=GradingViewSchema)
def get_grading_view(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Get all data needed for the grading view for a single submission."""
    submission = db.exec(select(QuizSubmission).where(QuizSubmission.id == submission_id).options(joinedload(QuizSubmission.student), joinedload(QuizSubmission.answers))).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    quiz = db.exec(select(Quiz).where(Quiz.id == submission.quiz_id).options(joinedload(Quiz.questions).joinedload(Question.options))).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz associated with submission not found")
    return GradingViewSchema(submission=submission, quiz=quiz)

@submission_router.put("/{submission_id}/grade", response_model=QuizSubmissionRead)
def grade_submission(
    submission_id: uuid.UUID,
    score: float,
    feedback: str = None,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Grade a student's quiz submission."""
    submission = db.get(QuizSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    submission.score = score
    submission.feedback = feedback
    submission.is_graded = True
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission
