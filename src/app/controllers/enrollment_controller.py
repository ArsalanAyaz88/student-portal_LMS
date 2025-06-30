# File: application/src/app/controllers/enrollment_controller.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from ..models.enrollment import Enrollment, get_pakistan_time
from src.app.models.course import Course
from ..schemas.payment_proof import ProofCreate
from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..models.payment_proof import PaymentProof
from ..models.notification import Notification
from datetime import datetime, timedelta
from ..utils.time import get_pakistan_time
import os
from uuid import uuid4
from ..schemas.enrollment import EnrollmentStatus
from ..utils.file import save_upload_and_get_url

router = APIRouter(
    prefix="/api/enrollments",
    tags=["Enrollments"]
)

from ..models.bank_account import BankAccount

@router.get("/courses/{course_id}/purchase-info")
def get_purchase_info(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    bank_accounts = session.exec(select(BankAccount).where(BankAccount.is_active == True)).all()
    return {
        "course_title": course.title,
        "course_price": course.price,
        "bank_accounts": [
            {
                "bank_name": acc.bank_name,
                "account_name": acc.account_name,
                "account_number": acc.account_number
            }
            for acc in bank_accounts
        ]
    }

@router.post("/{course_id}/payment-proof")
def submit_payment_proof(
    course_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    url = save_upload_and_get_url(file, folder="payment_proofs")
    # Check course
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Create pending enrollment if not exists
    enrollment = session.exec(select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_id)).first()
    if not enrollment:
        enrollment = Enrollment(user_id=user.id, course_id=course_id, status="pending", enroll_date=get_pakistan_time(), is_accessible=False, audit_log=[])
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)
    # Save payment proof
    payment_proof = PaymentProof(enrollment_id=enrollment.id, proof_url=url)
    session.add(payment_proof)
    session.commit()
    # Notify admin, include user details and picture URL in details
    try:
        notif = Notification(
            user_id=user.id,
            course_id=uuid.UUID(str(course_id)),  # Ensure course.id is converted to UUID
            event_type="payment_proof",
            timestamp=get_pakistan_time(),
            details=(
                f"Payment proof submitted for course {course.title} \n"
                f"User: {user.full_name or user.email} (User ID: {user.id})\n"
                f"Email: {user.email}\n"
                f"Proof image: {url}"
            ),
        )
        session.add(notif)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error creating notification: {str(e)}")
        raise
    session.add(notif)
    session.commit()
    return {"detail": "Payment proof submitted, pending admin approval."}

