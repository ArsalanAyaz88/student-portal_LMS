from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
import uuid
from typing import Optional
from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.course import Course
from src.app.models.enrollment_application import EnrollmentApplication, ApplicationStatus
from src.app.schemas.enrollment_application_schema import EnrollmentApplicationCreate, EnrollmentApplicationRead
from src.app.utils.file import upload_file_to_cloudinary
from src.app.utils.dependencies import get_current_user
from ..models.enrollment import Enrollment, get_pakistan_time
from src.app.models.course import Course
from ..schemas.payment_proof import ProofCreate
from ..db.session import get_db
from ..models.payment_proof import PaymentProof
from ..models.notification import Notification
from datetime import datetime, timedelta
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