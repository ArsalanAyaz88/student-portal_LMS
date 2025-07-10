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
    submit_assignment,
    get_submission
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

@router.get("", response_model=List[AssignmentRead])
def student_list(
    course_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_assignments(db, course_id, user.id)

@router.get("/{assignment_id}")
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
async def student_submit(
    course_id: UUID,
    assignment_id: UUID,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Save file & build payload
    content_url = await save_upload_and_get_url(file, folder="assignments")
    payload = SubmissionCreate(content_url=content_url)

    submit_assignment(db, course_id, assignment_id, user.id, payload)
    return {
        "message": "Assignment submitted successfully!"
    }

@router.get("/{assignment_id}/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission_details(
    course_id: UUID,
    assignment_id: UUID,
    submission_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific assignment submission
    """
    submission = get_submission(db, submission_id, user.id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found or access denied"
        )
    return submission
