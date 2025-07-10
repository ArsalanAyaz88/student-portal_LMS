# File: application/src/app/routers/student_assignment_router.py

import logging
from fastapi import APIRouter, Depends, UploadFile, File, status, HTTPException
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
    logger = logging.getLogger(__name__)
    logger.info(f"Submission attempt for assignment {assignment_id} by user {user.id}")

    try:
        # 1. Save file & build payload
        logger.info(f"Uploading file '{file.filename}' to Cloudinary.")
        content_url = await save_upload_and_get_url(file, folder="assignments")
        logger.info(f"File uploaded successfully. URL: {content_url}")

        # 2. Create submission payload
        payload = SubmissionCreate(content_url=content_url)
        logger.info("Submission payload created.")

        # 3. Call controller to save submission
        submission = submit_assignment(db, course_id, assignment_id, user.id, payload)
        logger.info(f"Submission saved to database with ID: {submission.id}")

        # 4. Return success response
        return {
            "message": "Assignment submitted successfully!",
            "submission": submission
        }

    except HTTPException as e:
        logger.error(f"HTTP Exception during submission: {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during submission: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during submission."
        )

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
