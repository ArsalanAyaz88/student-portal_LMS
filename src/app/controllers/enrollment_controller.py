

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
    prefix="/api/enrollments",
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





router = APIRouter(
    prefix="/api/enrollments",
    tags=["Enrollments"]
)

from ..models.bank_account import BankAccount
from ..models.user import User
import uuid


@router.get("/application-status/{course_id}", response_model=dict)
def get_application_status(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check the enrollment application status for a specific course for the current user.
    """
    application = db.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.course_id == course_id,
            EnrollmentApplication.user_id == current_user.id
        )
    ).first()

    if not application:
        return {"status": "not_found"}
    
    return {"status": application.status.value}


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
async def submit_payment_proof(
    course_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    url = await save_upload_and_get_url(file, folder="payment_proofs")
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

@router.post("/apply/{course_id}", response_model=EnrollmentApplicationRead)
async def apply_for_course(
    course_id: uuid.UUID,
    first_name: str = Form(...),
    last_name: str = Form(...),
    qualification: str = Form(...),
    contact_number: str = Form(...),
    ultrasound_experience: Optional[str] = Form(None),
    certificate: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
) -> EnrollmentApplication:
    # Check if course exists
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if user has already applied for this course
    existing_application = session.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == current_user.id,
            EnrollmentApplication.course_id == course_id
        )
    ).first()

    if existing_application:
        raise HTTPException(status_code=400, detail="You have already applied for this course.")

    # Upload certificate to Cloudinary
    file_id = f"enrollment_certificates/{current_user.id}_{course_id}_{uuid.uuid4()}"
    try:
        certificate_url = await upload_file_to_cloudinary(certificate.file, public_id=file_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload certificate: {str(e)}")

    application_data = EnrollmentApplicationCreate(
        first_name=first_name,
        last_name=last_name,
        qualification=qualification,
        contact_number=contact_number,
        ultrasound_experience=ultrasound_experience
    )

    # Create new enrollment application
    new_application = EnrollmentApplication(
        **application_data.dict(),
        user_id=current_user.id,
        course_id=course_id,
        qualification_certificate_url=certificate_url,
        status=ApplicationStatus.PENDING
    )

    session.add(new_application)
    session.commit()
    session.refresh(new_application)

    return new_application