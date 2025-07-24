from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlmodel import select
import uuid
import logging

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.course import Course
from src.app.models.enrollment_application import ApplicationStatus, EnrollmentApplication
from src.app.models.payment_proof import PaymentProof
from src.app.models.bank_account import BankAccount
from src.app.schemas.payment_proof import ProofCreate
from src.app.schemas.enrollment_application_schema import EnrollmentApplicationCreate, EnrollmentApplicationRead
from src.app.utils.dependencies import get_current_user
from src.app.models.notification import Notification


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/enrollments",
    tags=["enrollments"],
)

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

    # The schema now expects a URL, which the frontend provides after uploading.
    new_application = EnrollmentApplication.from_orm(application_data)
    new_application.user_id = current_user.id
    new_application.status = ApplicationStatus.PENDING
    
    db.add(new_application)

    # Create a notification for the admin
    notification = Notification(
        user_id=current_user.id, # The user who performed the action
        course_id=application_data.course_id,
        event_type="new_enrollment_application",
        details=f"New enrollment application from {current_user.name} for course: {application_data.course_id}."
    )
    db.add(notification)
    
    db.commit()
    db.refresh(new_application)

    notification_message = f"New enrollment application from {current_user.name} for course ID {application_data.course_id}."
    # Assuming create_admin_notification is available and works as intended
    # create_admin_notification(db, notification_message, current_user.id, new_application.id)

    return new_application


@router.post("/submit-payment-proof", response_model=PaymentProof, summary="Submit payment proof for an enrollment")
async def submit_payment_proof(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    course_id: uuid.UUID = Body(...),
    bank_account_id: uuid.UUID = Body(...),
    transaction_id: str = Body(...),
    file_url: str = Body(...)
):
    if current_user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can submit payment proofs")

    application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == course_id
        )
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="No application found for this course.")
    
    if application.status != ApplicationStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Your application must be approved before submitting payment.")

    proof = PaymentProof(
        user_id=current_user.id,
        course_id=course_id,
        bank_account_id=bank_account_id,
        transaction_id=transaction_id,
        proof_url=file_url, # Using the pre-uploaded file URL
        status='pending'
    )
    db.add(proof)

    # Create a notification for the admin
    notification = Notification(
        user_id=current_user.id,
        course_id=course_id,
        event_type="payment_proof_submitted",
        details=f"Payment proof submitted by {current_user.name} for course: {course_id}."
    )
    db.add(notification)

    db.commit()
    db.refresh(proof)
    
    notification_message = f"Payment proof submitted by {current_user.name} for course ID {course_id}."
    # create_admin_notification(db, notification_message, current_user.id, proof.id)

    return proof


@router.get("/{course_id}/status", summary="Check enrollment status for a course")
def get_application_status(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.course_id == course_id,
            EnrollmentApplication.user_id == current_user.id
        )
    ).first()

    if not application:
        return {"status": "not_applied"}
    
    return {"status": application.status.value}


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