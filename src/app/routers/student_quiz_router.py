# File: application/src/app/routers/student_quiz_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from uuid import UUID

from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..controllers import quiz_controller
from ..schemas.quiz import (
    QuizListRead,
    QuizDetailRead,
    QuizSubmissionCreate,
    QuizResult,
    QuizSubmissionRead,
)
from ..models.user import User
from ..models.quiz import QuizSubmission

# This router will handle all student-facing quiz interactions
router = APIRouter(
    prefix="/courses",
    tags=["Student Quizzes"],
)

@router.get(
    "/{course_id}/quizzes",
    response_model=List[QuizListRead],
    summary="List Quizzes for a Student in a Course",
)
def student_list_quizzes(
    course_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return quiz_controller.list_quizzes(db, course_id, current_user.id)


@router.get(
    "/courses/{course_id}/quizzes/{quiz_id}",
    response_model=QuizDetailRead,
    summary="Get a Single Quiz for a Student",
)
def student_get_quiz(
    course_id: UUID,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return quiz_controller.get_quiz_detail(db, course_id, quiz_id, current_user.id)


@router.post(
    "/courses/{course_id}/quizzes/{quiz_id}/submissions",
    response_model=QuizSubmission,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Quiz",
)
def student_submit_quiz(
    course_id: UUID,
    quiz_id: UUID,
    payload: QuizSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    submission = quiz_controller.submit_quiz(db, course_id, quiz_id, current_user.id, payload)
    return submission


@router.get(
    "/courses/{course_id}/quizzes/{quiz_id}/results/{submission_id}",
    response_model=QuizResult,
    summary="Get Quiz Result for a Student",
)
def get_quiz_result_route(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # These are in the path but not used by the controller
    course_id: UUID = None,
    quiz_id: UUID = None,
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    return quiz_controller.get_quiz_result(
        db=db,
        submission_id=submission_id,
        student_id=current_user.id
    )


@router.get(
    "/courses/{course_id}/submissions",
    response_model=List[QuizSubmissionRead],
    summary="List All Quiz Submissions for a Student in a Course",
)
def list_student_submissions(
    course_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return quiz_controller.list_submissions_for_student(db, course_id, current_user.id)
