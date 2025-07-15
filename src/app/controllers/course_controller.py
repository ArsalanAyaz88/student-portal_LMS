# File: application/src/app/controllers/course_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from src.app.models.course import Course
from src.app.models.user import User
from ..models.enrollment import Enrollment
from ..models.video import Video
from ..models.video_progress import VideoProgress
from ..models.course_progress import CourseProgress
from ..models.certificate import Certificate
from ..schemas.course import CourseRead, CourseListRead, CourseExploreList, CourseExploreDetail, CourseCurriculumDetail, CourseDetail, CurriculumSchema, OutcomesSchema, PrerequisitesSchema, CourseBasicDetail, DescriptionSchema
from ..schemas.course import VideoWithCheckpoint, CourseProgress as CourseProgressSchema
from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..utils.certificate_generator import CertificateGenerator
from fastapi.responses import FileResponse
import json
from datetime import datetime
import uuid
import os
from ..utils.time import get_pakistan_time
from fastapi import File, UploadFile
import cloudinary
import cloudinary.uploader
from fastapi.logger import logger

router = APIRouter(tags=["Courses"])


@router.get("/my-courses", response_model=list[CourseRead])
def get_my_courses(user=Depends(get_current_user), session: Session = Depends(get_db)):
    # Find all enrollments for the user that are approved, accessible and not expired
    current_time = get_pakistan_time()
    
    # Get all enrollments for the user
    enrollments = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "approved"
        )
    ).all()
    
    # Filter enrollments based on expiration
    valid_enrollments = []
    for enrollment in enrollments:
        enrollment.update_expiration_status()
        if enrollment.is_accessible:
            valid_enrollments.append(enrollment)
    
    # Create a map of course_id to expiration_date
    enrollment_map = {str(e.course_id): e.expiration_date for e in valid_enrollments}
    
    course_ids = [e.course_id for e in valid_enrollments]
    if not course_ids:
        return []
    
    # Return only the courses the user is enrolled in with required fields
    courses = session.exec(
        select(Course)
        .where(Course.id.in_(course_ids))
    ).all()
    
    # Create response with only required fields
    return [
        CourseRead(
            id=course.id,
            title=course.title,
            thumbnail_url=course.thumbnail_url,
            expiration_date=enrollment_map.get(str(course.id))
        ) for course in courses
    ]

# --- Explore Courses: List --
@router.get("/explore-courses", response_model=list[CourseExploreList])
def explore_courses(session: Session = Depends(get_db)):
    courses = session.exec(select(Course)).all()
    # Return only id, title, price, thumbnail_url
    return [
        CourseExploreList(
            id=course.id,
            title=course.title,
            price=course.price,
            thumbnail_url=course.thumbnail_url
        ) for course in courses
    ]

# --- Explore Courses: Detail ---
@router.get("/explore-courses/{course_id}", response_model=CourseExploreDetail)
def explore_course_detail(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseExploreDetail(
        id=course.id,
        title=course.title,
        price=course.price,
        thumbnail_url=course.thumbnail_url,
        description=course.description,
        outcomes=course.outcomes or "",
        prerequisites=course.prerequisites or "",
        curriculum=course.curriculum or ""
    )

# --- Enrollment Status ---
@router.get("/my-courses/{course_id}/enrollment-status", response_model=dict)
def get_enrollment_status(course_id: str, user=Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_uuid,
            Enrollment.status == "approved"
        )
    ).first()

    if enrollment:
        enrollment.update_expiration_status()
        if enrollment.is_accessible:
            return {"is_enrolled": True}

    return {"is_enrolled": False}

# --- Curriculum Text Endpoint ---
@router.get("/courses/{course_id}/curriculum", response_model=CurriculumSchema)
def get_course_curriculum(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CurriculumSchema(curriculum=course.curriculum or "")

@router.get("/courses/{course_id}/outcomes", response_model=OutcomesSchema)
def get_course_outcomes(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return OutcomesSchema(outcomes=course.outcomes or "")

@router.get("/courses/{course_id}/prerequisites", response_model=PrerequisitesSchema)
def get_course_prerequisites(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return PrerequisitesSchema(prerequisites=course.prerequisites or "")

# --- Description Text Endpoint ---
@router.get("/courses/{course_id}/description", response_model=DescriptionSchema)
def get_course_description(course_id: str, session: Session = Depends(get_db)):
    course = session.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return DescriptionSchema(description=course.description or "")


@router.get("/my-courses/{course_id}/videos-with-checkpoint", response_model=list[VideoWithCheckpoint])
def get_course_videos_with_checkpoint(
    course_id: str,
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        # Convert course_id to UUID
        course_uuid = uuid.UUID(course_id)
        
        # Fetch the enrollment record
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == course_uuid,
                Enrollment.status == "approved"
            )
        ).first()

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="You are not enrolled in this course."
            )

        # Get current time in Pakistan timezone
        current_time = get_pakistan_time()
        
        # An enrollment is not accessible if it has an expiration date that is in the past
        if enrollment.expiration_date:
            # Make both datetimes timezone-naive for comparison
            expiration_date = enrollment.expiration_date
            if expiration_date.tzinfo is not None:
                expiration_date = expiration_date.replace(tzinfo=None)
            
            if expiration_date < current_time.replace(tzinfo=None):
                raise HTTPException(
                    status_code=403,
                    detail="Your access to this course has expired."
                )
        
        # Also respect the is_accessible flag which might be set to false for other reasons.
        if not enrollment.is_accessible:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this course."
            )

        # Get course videos
        course = session.exec(
            select(Course)
            .where(Course.id == course_uuid)
            .options(selectinload(Course.videos))
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Get all video IDs
        video_ids = [video.id for video in course.videos]
        if not video_ids:
            return []

        # Get video progress
        progresses = session.exec(
            select(VideoProgress).where(
                VideoProgress.user_id == user.id,
                VideoProgress.video_id.in_(video_ids)
            )
        ).all()
        
        # Create progress map using UUIDs
        progress_map = {str(p.video_id): p.completed for p in progresses}

        # Build response
        result = []
        for video in course.videos:
            result.append(VideoWithCheckpoint(
                id=str(video.id),
                youtube_url=video.youtube_url,
                title=video.title,
                description=video.description,
                watched=progress_map.get(str(video.id), False)
            ))
        return result

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid course ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching course videos: {str(e)}"
        )



@router.post("/videos/{video_id}/complete")
def mark_video_completed(
    video_id: str,
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
): 
    try:
        # Validate video_id format
        try:
            video_uuid = uuid.UUID(video_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid video ID format"
            )

        # Check if video exists
        video = session.exec(
            select(Video).where(Video.id == video_uuid)
        ).first()
        
        if not video:
            raise HTTPException(
                status_code=404,
                detail="Video not found"
            )

        # Fetch the enrollment record
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == video.course_id,
                Enrollment.status == "approved"
            )
        ).first()

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="You are not enrolled in this course."
            )

        # Get current time in Pakistan timezone
        current_time = get_pakistan_time()
        
        # An enrollment is not accessible if it has an expiration date that is in the past
        if enrollment.expiration_date:
            # Make both datetimes timezone-naive for comparison
            expiration_date = enrollment.expiration_date
            if expiration_date.tzinfo is not None:
                expiration_date = expiration_date.replace(tzinfo=None)
            
            if expiration_date < current_time.replace(tzinfo=None):
                raise HTTPException(
                    status_code=403,
                    detail="Your access to this course has expired."
                )
        
        # Also respect the is_accessible flag which might be set to false for other reasons.
        if not enrollment.is_accessible:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this course."
            )
        
        # Get video progress
        progress = session.exec(
            select(VideoProgress).where(
                VideoProgress.user_id == user.id,
                VideoProgress.video_id == video_uuid
            )
        ).first()

        if progress:
            # Toggle the completed status
            progress.completed = not progress.completed
            action = "unmarked as" if not progress.completed else "marked as"
            session.add(progress) # Add to session to register change for commit
            message = f"Video {action} completed"
        else:
            # Create new progress entry as completed (first click)
            progress = VideoProgress(
                user_id=user.id,
                video_id=video_uuid,
                completed=True
            )
            session.add(progress)
            message = "Video marked as completed"

        session.commit()
        # Refresh the object to get the updated state if needed, though for just returning a message it's not strictly necessary
        # session.refresh(progress)
        return {"detail": message}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing video completion status: {str(e)}"
        )




@router.get("/courses/{course_id}/certificate")
async def get_certificate(
    course_id: str,
    name: str,  # Accept name from query parameter
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        # 1. Validate course_id
        try:
            course_uuid = uuid.UUID(course_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid course ID format")

        # 2. Check enrollment and completion
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.student_id == user.id, 
                Enrollment.course_id == course_uuid
            )
        ).first()
        if not enrollment:
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")
        if not enrollment.is_completed:
            raise HTTPException(status_code=403, detail="You must complete the course to get a certificate")

        # 3. Delete existing certificate if it exists
        existing_certificate = session.exec(
            select(Certificate).where(
                Certificate.user_id == user.id, 
                Certificate.course_id == course_uuid
            )
        ).first()
        if existing_certificate:
            session.delete(existing_certificate)
            session.commit()

        # 4. Generate a new certificate with the provided name
        course = session.get(Course, course_uuid)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        student_name = name
        if not student_name or student_name.lower() == 'string':
            raise HTTPException(status_code=400, detail="A valid name is required for the certificate.")

        try:
            certificate_generator = CertificateGenerator()
            certificate_url = await certificate_generator.generate(
                username=student_name,
                course_title=course.title,
                completion_date=str(get_pakistan_time().date())
            )

            new_certificate = Certificate(
                user_id=user.id,
                course_id=course_uuid,
                file_path=certificate_url,
                certificate_number=os.path.basename(certificate_url).split('/')[-1].replace('certificate_', '').replace('.pdf', '')
            )
            session.add(new_certificate)
            session.commit()
            session.refresh(new_certificate)

            return {
                "certificate_url": new_certificate.file_path,
                "certificate_number": new_certificate.certificate_number
            }
        except Exception as e:
            # Log the full error for debugging
            print(f"Certificate generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Error generating certificate: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Certificate retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/courses/{course_id}/thumbnail", response_model=CourseRead)
def upload_course_thumbnail(
    course_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    # Assuming you have a dependency to get an admin/instructor user
    # For now, we'll use get_current_user and you can restrict it later
    user=Depends(get_current_user)
):
    """
    Uploads a thumbnail for a specific course to Cloudinary and updates the database.
    This endpoint should be restricted to admins or course instructors.
    """
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid course ID format"
        )

    course = session.exec(select(Course).where(Course.id == course_uuid)).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # TODO: Add authorization check to ensure the user is an admin or instructor

    try:
        # Upload image to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            folder="course_thumbnails",
            public_id=f"{course_id}_thumbnail",
            overwrite=True,
            resource_type="image"
        )
        secure_url = upload_result.get('secure_url')

        if not secure_url:
            raise HTTPException(status_code=500, detail="Cloudinary upload failed: No URL returned.")

        # Update course thumbnail_url
        course.thumbnail_url = secure_url
        session.add(course)
        session.commit()
        session.refresh(course)

        # Return the updated course details
        return CourseRead(
            id=course.id,
            title=course.title,
            thumbnail_url=course.thumbnail_url,
            # Expiration date is not relevant here, but the model requires it
            expiration_date=None 
        )

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during thumbnail upload: {str(e)}"
        )