from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlmodel import select
import uuid
import logging
import traceback
import os
from datetime import datetime
from pydantic import BaseModel

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.course import Course
from src.app.models.enrollment import Enrollment
from src.app.models.enrollment_application import EnrollmentApplication, ApplicationStatus
from src.app.models.bank_account import BankAccount
from src.app.models.notification import Notification
from src.app.models.payment_proof import PaymentProof, PaymentStatus
from src.app.schemas.enrollment_application_schema import (
    EnrollmentApplicationCreate,
    EnrollmentApplicationRead,
)
from src.app.utils.dependencies import get_current_user
from src.app.utils.file import save_upload_and_get_url

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Single, non-prefixed router. The prefix is applied in main.py.
router = APIRouter(prefix="/enrollments")

class EnrollmentStatusResponse(BaseModel):
    status: str
    application_id: uuid.UUID | None

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

@router.post("/apply", response_model=EnrollmentApplicationRead, summary="Apply for a course enrollment")
async def apply_for_enrollment(
    first_name: str = Form(...),
    last_name: str = Form(...),
    qualification: str = Form(...),
    ultrasound_experience: str = Form(None),
    contact_number: str = Form(...),
    course_id: str = Form(...),
    qualification_certificate: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can apply for enrollment")

    # Validate file type
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'}
    file_extension = os.path.splitext(qualification_certificate.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 10MB)
    if qualification_certificate.size and qualification_certificate.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size too large. Maximum size is 10MB."
        )

    # Upload qualification certificate to S3
    certificate_url = await save_upload_and_get_url(qualification_certificate, folder="qualification_certificates")

    # Convert course_id string to UUID
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    existing_application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == course_uuid
        )
    ).first()

    if existing_application:
        raise HTTPException(status_code=400, detail="You have already applied for this course")

    # Create new application with form data
    new_application = EnrollmentApplication(
        first_name=first_name,
        last_name=last_name,
        qualification=qualification,
        ultrasound_experience=ultrasound_experience,
        contact_number=contact_number,
        course_id=course_uuid,
        user_id=current_user.id,
        status=ApplicationStatus.PENDING,
        qualification_certificate_url=certificate_url
    )
    
    db.add(new_application)

    notification = Notification(
        user_id=current_user.id,
        course_id=course_uuid,
        event_type="new_enrollment_application",
        details=f"New enrollment application from {current_user.full_name or current_user.email} for course: {course_uuid}. Certificate uploaded: {certificate_url}"
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
    logger.info(f"[SUBMIT_PROOF_START] User '{user.id}' submitting proof for course '{course_id}'.")
    try:
        url = await save_upload_and_get_url(file, folder="payment_proofs")
        logger.info(f"[SUBMIT_PROOF] File uploaded to S3, URL: {url}")

        user = session.merge(user)
        course_uuid = uuid.UUID(course_id)
        
        course = session.get(Course, course_uuid)
        if not course:
            logger.error(f"[SUBMIT_PROOF_FAIL] Course with ID '{course_id}' not found.")
            raise HTTPException(status_code=404, detail="Course not found")

        application = session.exec(
            select(EnrollmentApplication).where(
                EnrollmentApplication.user_id == user.id,
                EnrollmentApplication.course_id == course_uuid,
                EnrollmentApplication.status == ApplicationStatus.APPROVED
            )
        ).first()

        if not application:
            logger.error(f"[SUBMIT_PROOF_FAIL] User '{user.id}' application for course '{course_id}' not approved.")
            raise HTTPException(status_code=403, detail="Your application is not approved. You cannot submit payment proof.")

        enrollment = session.exec(
            select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_uuid)
        ).first()

        if not enrollment:
            logger.info(f"[SUBMIT_PROOF] No existing enrollment found for user '{user.id}' and course '{course_id}'. Creating new one.")
            enrollment = Enrollment(
                user_id=user.id, 
                course_id=course_uuid, 
                enroll_date=datetime.utcnow(), 
                is_accessible=False,
                status="pending"
            )
            session.add(enrollment)
        else:
            logger.info(f"[SUBMIT_PROOF] Found existing enrollment: {enrollment.id}")

        payment_proof = PaymentProof(
            proof_url=url,
            status=PaymentStatus.PENDING,
            enrollment=enrollment
        )
        session.add(payment_proof)
        
        notif = Notification(
            user_id=user.id,
            course_id=course_uuid,
            event_type="payment_proof",
            details=f"Payment proof submitted for course {course.title}. User: {user.full_name or user.email} (ID: {user.id}). Proof: {url}"
        )
        session.add(notif)
        
        logger.info("[SUBMIT_PROOF] Committing transaction...")
        session.commit()
        logger.info("[SUBMIT_PROOF] Commit successful.")

        session.refresh(enrollment)
        session.refresh(payment_proof)
        
        logger.info(f"[SUBMIT_PROOF_SUCCESS] Refreshed Enrollment ID: {enrollment.id}, PaymentProof ID: {payment_proof.id}, Linked Enrollment ID: {payment_proof.enrollment_id}")
        return {"detail": "Payment proof submitted, pending admin approval.", "status": "pending"}
        
    except Exception as e:
        logger.error(f"[SUBMIT_PROOF_EXCEPTION] An unexpected error occurred: {e}")
        logger.error(traceback.format_exc())
        session.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred. Please check logs for details.")

@router.get("/enrollments/{course_id}/payment-proof/status", summary="Check payment proof status for a course")
def get_payment_proof_status(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"[GET_STATUS_START] User '{current_user.id}' checking status for course '{course_id}'.")
    
    enrollment = db.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.user_id == current_user.id
        )
    ).first()

    if not enrollment:
        logger.warning(f"[GET_STATUS_FAIL] No enrollment record found for user '{current_user.id}' and course '{course_id}'.")
        raise HTTPException(
            status_code=404, 
            detail="Enrollment not found. No payment proof submitted."
        )
    
    logger.info(f"[GET_STATUS] Found enrollment record with ID: {enrollment.id}. Checking for linked payment proofs.")
    
    if enrollment.payment_proofs:
        logger.info(f"[GET_STATUS] Found {len(enrollment.payment_proofs)} payment proof(s) on the relationship.")
        payment_proof = sorted(enrollment.payment_proofs, key=lambda p: p.submitted_at, reverse=True)[0]
        logger.info(f"[GET_STATUS_SUCCESS] Latest proof found with ID: {payment_proof.id} and status: '{payment_proof.status.value}'.")
        return {"status": payment_proof.status.value}
    else:
        logger.warning(f"[GET_STATUS_FAIL] Enrollment {enrollment.id} found, but it has no linked payment proofs.")
        raise HTTPException(
            status_code=404, 
            detail="Payment proof not yet submitted."
        )

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