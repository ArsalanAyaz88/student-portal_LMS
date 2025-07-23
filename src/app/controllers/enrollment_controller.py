

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from typing import Optional
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import selectinload

from ..db.session import get_db
from ..utils.email import send_application_approved_email, send_enrollment_rejected_email
from ..models.user import User
from ..models.course import Course
from ..models.enrollment_application import EnrollmentApplication, ApplicationStatus
from ..models.payment_proof import PaymentProof
from ..models.bank_account import BankAccount
from ..schemas.enrollment_application_schema import EnrollmentApplicationCreate, EnrollmentApplicationRead
from ..utils.dependencies import get_current_user
from ..utils.file import upload_file_to_cloudinary
from ..utils.dependencies import get_current_admin_user
from ..schemas.enrollment_application_schema import EnrollmentApplicationUpdate
from ..models.enrollment import Enrollment

router = APIRouter(
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
            logger.warning(f"No application found for course_id: {course_id} and user_id: {current_user.id}. Raising 404.")
            raise HTTPException(status_code=404, detail="Application not found")
        
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


@router.get("/admin/applications", response_model=list[EnrollmentApplicationRead])
def get_all_applications(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Retrieve all enrollment applications. Admin access required.
    """
    applications = db.exec(select(EnrollmentApplication)).all()
    return applications


@router.patch("/admin/applications/{application_id}", response_model=EnrollmentApplicationRead)
def update_application_status(
    application_id: uuid.UUID,
    application_update: EnrollmentApplicationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Update the status of an enrollment application (approve or reject). Admin access required.
    """
    # Eagerly load user and course relationships to get email and title
    query = (
        select(EnrollmentApplication)
        .options(
            selectinload(EnrollmentApplication.user),
            selectinload(EnrollmentApplication.course)
        )
        .where(EnrollmentApplication.id == application_id)
    )
    application = db.exec(query).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    original_status = application.status
    application.status = application_update.status
    db.add(application)

    # If approved for the first time, create a corresponding enrollment record
    if application.status == ApplicationStatus.APPROVED and original_status != ApplicationStatus.APPROVED:
        existing_enrollment = db.exec(
            select(Enrollment).where(
                Enrollment.user_id == application.user_id,
                Enrollment.course_id == application.course_id
            )
        ).first()

        if not existing_enrollment:
            new_enrollment = Enrollment(
                user_id=application.user_id,
                course_id=application.course_id,
                status="pending"  # User still needs to pay
            )
            db.add(new_enrollment)

    db.commit()

    # Send email notification
    try:
        if application.status == ApplicationStatus.APPROVED:
            send_application_approved_email(
                to_email=application.user.email,
                course_title=application.course.title
            )
        elif application.status == ApplicationStatus.REJECTED:
            send_enrollment_rejected_email(
                to_email=application.user.email,
                course_title=application.course.title,
                rejection_reason=application_update.rejection_reason or "No reason provided."
            )
    except Exception as e:
        logger.error(f"Failed to send email notification for application {application.id}: {e}")
        # Do not fail the request if email fails, but log it.

    db.refresh(application)
    return application
