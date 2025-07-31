from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.orm import Session
from sqlmodel import select
import uuid
import logging
from datetime import datetime
from pydantic import BaseModel

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.course import Course
from src.app.models.enrollment import Enrollment
from src.app.models.enrollment_application import EnrollmentApplication, ApplicationStatus
from src.app.models.bank_account import BankAccount
from src.app.models.notification import Notification
from src.app.models.payment_proof import PaymentProof
from src.app.schemas.enrollment_application_schema import (
    EnrollmentApplicationCreate,
    EnrollmentApplicationRead,
)
from src.app.utils.dependencies import get_current_user
from src.app.utils.file import save_upload_and_get_url

# Single, non-prefixed router. The prefix is applied in main.py.
router = APIRouter(prefix="/enrollments")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnrollmentStatusResponse(BaseModel):
    status: str
    application_id: uuid.UUID | None

@router.post("/apply", response_model=EnrollmentApplicationRead, summary="Apply for a course enrollment")
def apply_for_enrollment(
    application_data: EnrollmentApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can apply for enrollment")

    existing_application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == application_data.course_id
        )
    ).first()

    if existing_application:
        raise HTTPException(status_code=400, detail="You have already applied for this course")

    new_application = EnrollmentApplication.from_orm(application_data)
    new_application.user_id = current_user.id
    new_application.status = ApplicationStatus.PENDING
    
    db.add(new_application)

    notification = Notification(
        user_id=current_user.id,
        course_id=application_data.course_id,
        event_type="new_enrollment_application",
        details=f"New enrollment application from {current_user.name} for course: {application_data.course_id}."
    )
    db.add(notification)
    
    db.commit()
    db.refresh(new_application)

    return new_application

@router.post("/{course_id}/payment-proof")
async def submit_payment_proof(
    course_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    url = await save_upload_and_get_url(file, folder="payment_proofs")
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = session.exec(select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_uuid)).first()
    if not enrollment:
        enrollment = Enrollment(user_id=user.id, course_id=course_uuid, status="pending", enroll_date=datetime.utcnow(), is_accessible=False)
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)

    payment_proof = PaymentProof(enrollment_id=enrollment.id, proof_url=url)
    session.add(payment_proof)
    
    notif = Notification(
        user_id=user.id,
        course_id=course.id,
        event_type="payment_proof",
        details=f"Payment proof submitted for course {course.title}. User: {user.full_name or user.email} (ID: {user.id}). Proof: {url}"
    )
    session.add(notif)
    session.commit()
    return {"detail": "Payment proof submitted, pending admin approval."}

@router.get("/enrollments/{enrollment_id}/status", response_model=EnrollmentStatusResponse, summary="Check enrollment status by enrollment ID")
def get_enrollment_status_by_id(
    enrollment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.id == enrollment_id,
            EnrollmentApplication.user_id == current_user.id
        )
    ).first()
    
    if application:
        return {"status": application.status.value, "application_id": application.id}
    
    raise HTTPException(status_code=404, detail="Application not found")

@router.get("/courses/{course_id}/purchase-info", summary="Get course price and bank details for payment")
def get_purchase_info(course_id: uuid.UUID, session: Session = Depends(get_db)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    bank_accounts = session.exec(select(BankAccount).where(BankAccount.is_active == True)).all()
    if not bank_accounts:
        raise HTTPException(status_code=404, detail="No active bank accounts found for payment.")
        
    return {
        "course_price": course.price,
        "bank_accounts": [
            {
                "id": acc.id,
                "bank_name": acc.bank_name,
                "account_title": acc.account_name,
                "account_number": acc.account_number,
                "iban": acc.iban
            } for acc in bank_accounts
        ]
    }