from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from typing import List
import uuid

from src.app.db.session import get_db
from src.app.utils.dependencies import get_current_admin_user
from src.app.models.course import Course
from src.app.models.quiz import Quiz, Question, Option, QuizSubmission, Answer
from src.app.schemas.quiz import (
    QuizCreate, QuizRead, QuizUpdate,
    QuestionCreate, QuestionRead,
    QuizReadWithDetails,
    QuizSubmissionRead, QuizSubmissionReadWithStudent, QuizSubmissionReadWithDetails,
    GradingViewSchema
)

router = APIRouter()

#
# Quiz Management Endpoints
#

@router.post("/courses/{course_id}/quizzes", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def create_quiz_for_course(
    course_id: uuid.UUID,
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Create a new quiz for a specific course.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    
    new_quiz = Quiz.from_orm(quiz_data, update={'course_id': course_id})
    
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    return new_quiz

@router.get("/courses/{course_id}/quizzes")
def get_quizzes_for_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get all quizzes for a specific course.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    statement = select(Quiz).where(Quiz.course_id == course_id)
    quizzes = db.exec(statement).all()

    # Manually construct the response to bypass serialization issues.
    response_data = [
        {
            "id": str(quiz.id),
            "course_id": str(quiz.course_id),
            "title": quiz.title,
            "description": quiz.description,
            "due_date": quiz.due_date.isoformat() if quiz.due_date else None
        }
        for quiz in quizzes
    ]
    return JSONResponse(content=response_data)

@router.get("/quizzes/{quiz_id}", response_model=QuizReadWithDetails)
def get_quiz_details(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get detailed information about a specific quiz, including its questions and options.
    """
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return quiz

@router.put("/quizzes/{quiz_id}", response_model=QuizRead)
def update_quiz(
    quiz_id: uuid.UUID,
    quiz_data: QuizUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Update a quiz's details.
    """
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    
    quiz_update_data = quiz_data.dict(exclude_unset=True)
    for key, value in quiz_update_data.items():
        setattr(quiz, key, value)
    
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz

@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Delete a quiz.
    """
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    
    db.delete(quiz)
    db.commit()
    return

#
# Question Management Endpoints
#

@router.post("/quizzes/{quiz_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def add_question_to_quiz(
    quiz_id: uuid.UUID,
    question_data: QuestionCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Add a new question to a specific quiz.
    """
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    # Create options first
    options_data = question_data.options
    question_data_dict = question_data.dict()
    del question_data_dict['options']

    new_question = Question(**question_data_dict, quiz_id=quiz_id)
    db.add(new_question)
    db.commit()
    db.refresh(new_question)

    for option_data in options_data:
        new_option = Option(**option_data.dict(), question_id=new_question.id)
        db.add(new_option)
    
    db.commit()
    db.refresh(new_question)

    return new_question

@router.put("/questions/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: uuid.UUID,
    question_data: QuestionCreate, # Reusing create schema for simplicity
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Update a question's text, type, points, and options.
    """
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    # Update question fields
    question.text = question_data.text
    question.question_type = question_data.question_type
    question.points = question_data.points

    # Delete old options
    for option in question.options:
        db.delete(option)

    # Create new options
    for option_data in question_data.options:
        new_option = Option(**option_data.dict(), question_id=question.id)
        db.add(new_option)

    db.commit()
    db.refresh(question)
    return question

@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Delete a question.
    """
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    
    db.delete(question)
    db.commit()
    return

#
# Submission and Grading Endpoints
#

@router.get("/quizzes/{quiz_id}/submissions", response_model=List[QuizSubmissionReadWithStudent])
def get_quiz_submissions(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get all submissions for a specific quiz, including student details.
    """
    statement = (
        select(QuizSubmission)
        .where(QuizSubmission.quiz_id == quiz_id)
        .options(joinedload(QuizSubmission.student))
        .order_by(QuizSubmission.submitted_at.desc())
    )
    submissions = db.exec(statement).all()
    return submissions


@router.get("/submissions/{submission_id}/grading-view", response_model=GradingViewSchema)
def get_grading_view(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get all data needed for the grading view for a single submission.
    """
    # Fetch submission with student and answers
    submission_statement = (
        select(QuizSubmission)
        .where(QuizSubmission.id == submission_id)
        .options(
            joinedload(QuizSubmission.student),
            joinedload(QuizSubmission.answers)
        )
    )
    submission = db.exec(submission_statement).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Fetch the full quiz details
    quiz_statement = (
        select(Quiz)
        .where(Quiz.id == submission.quiz_id)
        .options(
            joinedload(Quiz.questions).joinedload(Question.options)
        )
    )
    quiz = db.exec(quiz_statement).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz associated with submission not found")

    return GradingViewSchema(submission=submission, quiz=quiz)


@router.put("/submissions/{submission_id}/grade", response_model=QuizSubmissionRead)
def grade_submission(
    submission_id: uuid.UUID,
    score: float,
    feedback: str = None,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Grade a student's quiz submission.
    """
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
