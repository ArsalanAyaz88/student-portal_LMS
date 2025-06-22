# File: application/src/app/routers/student_quiz_router.py

from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from uuid import UUID
from typing import List

from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..controllers.quiz_controller import (
    list_quizzes,
    get_quiz_detail,
    submit_quiz,
    get_quiz_result,
)
from ..schemas.quiz import (
    QuizListRead,
    QuizDetailRead,
    QuizSubmissionCreate,
    QuizResult,
)

router = APIRouter(
    prefix="/courses/{course_id}/quizzes",
    tags=["student_quizzes"],
)


@router.get("", response_model=List[QuizListRead])
def student_list_quizzes(
    course_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return list_quizzes(db, course_id, user.id)


@router.get("/{quiz_id}", response_model=QuizDetailRead)
def student_get_quiz(
    course_id: UUID,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return get_quiz_detail(db, course_id, quiz_id, user.id)


@router.post(
    "/{quiz_id}/submissions",
    response_model=QuizResult,
    status_code=status.HTTP_201_CREATED
)
def student_submit_quiz(
    course_id: UUID,
    quiz_id: UUID,
    payload: QuizSubmissionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return submit_quiz(db, course_id, quiz_id, user.id, payload)


@router.get(
    "/{quiz_id}/results/{submission_id}",
    response_model=QuizResult
)
def student_get_quiz_result(
    course_id: UUID,
    quiz_id: UUID,
    submission_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return get_quiz_result(db, course_id, quiz_id, submission_id, user.id)
