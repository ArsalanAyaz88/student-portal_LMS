from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from typing import List
import uuid
import logging
from typing import List

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.quiz import Quiz, Question, Option, QuizSubmission
from src.app.models.course import Course
from src.app.schemas.quiz import (
    QuizCreate, QuizRead, QuizUpdate, 
    QuestionCreate, QuestionRead, QuestionUpdate, 
    QuizSubmissionCreate, QuizSubmissionRead, GradeSubmissionRequest,
    QuizReadWithDetails, QuizSubmissionReadWithStudent, GradingViewSchema
)
from src.app.utils.dependencies import get_current_admin_user

# --- Router Definitions ---
# Using distinct routers for each resource type for a clean, RESTful API design.
quiz_router = APIRouter(tags=["Admin Quizzes"])
question_router = APIRouter(tags=["Admin Questions"])
submission_router = APIRouter(tags=["Admin Submissions"])


# --- Quiz Management Endpoints ---

@quiz_router.get("", response_model=List[QuizRead])
def list_quizzes(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Lists all quizzes for a specific course."""
    if not db.get(Course, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    
    statement = select(Quiz).where(Quiz.course_id == course_id)
    quizzes = db.exec(statement).all()
    return quizzes

@quiz_router.post("", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Creates a new quiz, including its questions and options, in a single transaction."""
    # Basic validation
    if not quiz_data.course_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Course ID is required."
        )
    if not db.get(Course, quiz_data.course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Separate quiz data from questions data
    quiz_dict = quiz_data.model_dump(exclude={'questions'})
    new_quiz = Quiz(**quiz_dict)
    db.add(new_quiz)

    # Process questions and options
    for question_data in quiz_data.questions:
        question_dict = question_data.model_dump(exclude={'options'})
        new_question = Question(**question_dict, quiz=new_quiz)
        db.add(new_question)

        for option_data in question_data.options:
            new_option = Option(**option_data.model_dump(), question=new_question)
            db.add(new_option)

    try:
        db.commit()
        db.refresh(new_quiz)
        return new_quiz
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating quiz: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the quiz."
        )

@quiz_router.get("/{quiz_id}", response_model=QuizReadWithDetails)
def get_quiz_details(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Gets detailed information about a specific quiz, including its questions and options."""
    statement = select(Quiz).where(Quiz.id == quiz_id).options(
        joinedload(Quiz.questions).joinedload(Question.options)
    )
    quiz = db.exec(statement).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return quiz

@quiz_router.get("/{quiz_id}/submissions", response_model=List[QuizSubmissionReadWithStudent])
def get_quiz_submissions(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Get all submissions for a specific quiz."""
    logging.info(f"Fetching submissions for quiz ID: {quiz_id}")
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        logging.warning(f"Quiz not found for ID: {quiz_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    try:
        statement = select(QuizSubmission).where(QuizSubmission.quiz_id == quiz_id).options(joinedload(QuizSubmission.student)).order_by(QuizSubmission.submitted_at.desc())
        submissions = db.exec(statement).all()
        logging.info(f"Found {len(submissions)} submissions for quiz ID: {quiz_id}")
        return submissions
    except Exception as e:
        logging.error(f"An error occurred fetching submissions for quiz ID {quiz_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch submissions")

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
    try:
        # Validate input data
        if not question_data.text or not question_data.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question text cannot be empty"
            )
            
        if not question_data.options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one option is required"
            )
            
        # Verify quiz exists
        quiz = db.get(Quiz, quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz with ID {quiz_id} not found"
            )

        # Validate there's exactly one correct option
        correct_options = [opt for opt in question_data.options if opt.is_correct]
        if len(correct_options) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one correct option is required"
            )

        # Create the question
        new_question = Question(
            text=question_data.text.strip(),
            quiz_id=quiz_id,
            is_multiple_choice=len(question_data.options) > 1
        )
        
        # Validate and prepare options
        options_to_add = []
        for i, opt in enumerate(question_data.options):
            if not opt.text or not opt.text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Option {i+1} text cannot be empty"
                )
            options_to_add.append(
                Option(
                    text=opt.text.strip(),
                    is_correct=opt.is_correct,
                    question=new_question
                )
            )
        
        # Add to database
        db.add(new_question)
        db.add_all(options_to_add)
        db.commit()
        db.refresh(new_question)
        
        # Eager load options for the response
        db.refresh(new_question, ['options'])
        
        return new_question
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        logging.error(f"Error adding question to quiz {quiz_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add question: {str(e)}"
        )


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
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin_user)
):
    """Grade a student's quiz submission."""
    submission = db.get(QuizSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    submission.score = score
    submission.is_graded = True
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission
