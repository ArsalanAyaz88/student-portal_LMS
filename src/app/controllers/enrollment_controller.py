

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from typing import Optional
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from ..db.session import get_db
from ..models.user import User
from ..models.course import Course
from ..models.enrollment_application import EnrollmentApplication, ApplicationStatus
from ..models.payment_proof import PaymentProof
from ..models.bank_account import BankAccount
from ..schemas.enrollment_application_schema import EnrollmentApplicationCreate, EnrollmentApplicationRead
from ..utils.dependencies import get_current_user
from ..utils.file import upload_file_to_cloudinary

router = APIRouter(
    prefix="/enrollments",
    tags=["Enrollments"]
)

@router.get("/application-status/{course_id}", response_model=dict)
def get_application_status(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check the enrollment application status for a specific course for the current user.
    """
    logger.info(f"Checking application status for course_id: {course_id} and user_id: {current_user.id}")
    try:
        application = db.exec(
            select(EnrollmentApplication).where(
                EnrollmentApplication.course_id == course_id,
                EnrollmentApplication.user_id == current_user.id
            )
        ).first()

        if not application:
            logger.warning(f"No application found for course_id: {course_id} and user_id: {current_user.id}. Returning 'not_found'.")
            return {"status": "not_found"}
        
        logger.info(f"Application found with status: {application.status.value}. Returning status.")
        return {"status": application.status.value}
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_application_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.get("/courses/{course_id}/purchase-info")
def get_purchase_info(course_id: uuid.UUID, session: Session = Depends(get_db)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    bank_account = session.exec(select(BankAccount)).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account details not found.")

    return {
        "course_price": course.price,
        "account_title": bank_account.account_title,
        "account_number": bank_account.account_number,
        "bank_name": bank_account.bank_name
    }

@router.post("/apply", response_model=EnrollmentApplicationRead)
def apply_for_enrollment(
    application_data: EnrollmentApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing_application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == application_data.course_id
        )
    ).first()

    if existing_application:
        raise HTTPException(
            status_code=400,
            detail="You have already applied for this course."
        )

    new_application = EnrollmentApplication.from_orm(application_data)
    new_application.user_id = current_user.id
    new_application.status = ApplicationStatus.PENDING
    
    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    return new_application

@router.post("/submit-payment-proof", status_code=201)
async def submit_payment_proof(
    course_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == course_id
        )
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Enrollment application not found.")

    file_url = await upload_file_to_cloudinary(file, "payment_proofs")

    proof = PaymentProof(
        application_id=application.id,
        proof_url=file_url,
        uploaded_at=datetime.now()
    )
    db.add(proof)
    db.commit()

    return {"message": "Payment proof submitted successfully."}




