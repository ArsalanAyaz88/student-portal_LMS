# File: application/src/app/controllers/assignment_controller.py

from sqlmodel import Session, select
from uuid import UUID
from fastapi import HTTPException, status
from datetime import datetime

from ..models.assignment import Assignment, AssignmentSubmission
from ..models.enrollment import Enrollment
from ..schemas.assignment import SubmissionCreate

def _ensure_enrollment(db: Session, course_id: UUID, student_id: UUID):
    """Raise 403 if the student isn't approved + accessible for this course."""
    stmt = (
        select(Enrollment)
        .where(
            Enrollment.course_id     == course_id,
            Enrollment.user_id       == student_id,
            Enrollment.status        == "approved",
            Enrollment.is_accessible == True,
        )
    )
    if not db.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="🚫 You are not enrolled in this course."
        )

def list_assignments(db: Session, course_id: UUID, student_id: UUID):
    # 1️⃣ check enrollment
    _ensure_enrollment(db, course_id, student_id)

    # 2️⃣ return all assignments for that course
    return db.exec(
        select(Assignment).where(Assignment.course_id == course_id)
    ).all()

def get_assignment(db: Session, course_id: UUID, assignment_id: UUID, student_id: UUID):
    # 1️⃣ check enrollment
    _ensure_enrollment(db, course_id, student_id)

    # 2️⃣ load & validate assignment
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    return assignment

def get_submission(db: Session, submission_id: UUID, student_id: UUID):
    """
    Get a specific submission by ID, ensuring the requesting student is the owner
    """
    submission = db.get(AssignmentSubmission, submission_id)
    
    # Check if submission exists and belongs to the student
    if not submission or submission.student_id != student_id:
        return None
        
    return submission

def submit_assignment(
    db: Session,
    course_id: UUID,
    assignment_id: UUID,
    student_id: UUID,
    payload: SubmissionCreate
):
    # 1️⃣ check enrollment
    _ensure_enrollment(db, course_id, student_id)

    # 2️⃣ load assignment & enforce deadline
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    # Get current time in Pakistan timezone
    from ..utils.time import get_pakistan_time
    now = get_pakistan_time()
    
    # Make both datetimes timezone-naive for comparison
    due_date = assignment.due_date
    if due_date.tzinfo is not None:
        due_date = due_date.replace(tzinfo=None)
    
    if now.replace(tzinfo=None) > due_date:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="⏰ The due date has passed. You can no longer submit this assignment."
        )

    # 3️⃣ prevent double submit
    existing = db.exec(
        select(AssignmentSubmission)
        .where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id    == student_id
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="📌 You have already submitted this assignment."
        )

    # 4️⃣ create & return
    sub = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=student_id,
        content_url=payload.content_url
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # To prevent circular dependency issues during serialization,
    # return a new object without the nested 'assignment' relationship.
    return AssignmentSubmission.from_orm(sub)
