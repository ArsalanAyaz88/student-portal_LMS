# File: application/src/app/routers/student_assignment_router.py

from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlmodel import Session
from uuid import UUID
from typing import List
from ..utils.file import save_upload_and_get_url

from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..controllers.assignment_controller import (
    list_assignments,
    get_assignment,
    submit_assignment
)
from ..models.assignment import AssignmentSubmission
from ..schemas.assignment import (
    AssignmentList,
    AssignmentRead,
    SubmissionCreate,
    SubmissionRead,
    SubmissionResponse,
)

router = APIRouter(
    prefix="/courses/{course_id}/assignments",
    tags=["student_assignments"],
)

@router.get("", response_model=List[AssignmentList])
def student_list(
    course_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_assignments(db, course_id, user.id)

@router.get("/{assignment_id}", response_model=AssignmentRead)
def student_detail(
    course_id: UUID,
    assignment_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_assignment(db, course_id, assignment_id, user.id)

@router.post(
    "/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED
)
def student_submit(
    course_id: UUID,
    assignment_id: UUID,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Save file & build payload
    content_url = save_upload_and_get_url(file, folder="assignments")
    payload = SubmissionCreate(content_url=content_url)

    sub_obj = submit_assignment(db, course_id, assignment_id, user.id, payload)
    return SubmissionResponse(
        message="✅ Assignment submitted successfully!",
        submission=SubmissionRead.from_orm(sub_obj)
    )
