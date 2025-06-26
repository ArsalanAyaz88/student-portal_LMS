# File: application/src/app/controllers/course_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from src.app.models.course import Course
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
from fastapi import File

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


@router.get("/my-courses/{course_id}/videos", response_model=list[VideoWithCheckpoint])
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

        # Manually check expiration status in memory
        current_time = get_pakistan_time().replace(tzinfo=None)
        
        # An enrollment is not accessible if it has an expiration date that is in the past.
        if enrollment.expiration_date and enrollment.expiration_date < current_time:
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

        # Manually check expiration status in memory
        current_time = get_pakistan_time().replace(tzinfo=None)
        
        # An enrollment is not accessible if it has an expiration date that is in the past.
        if enrollment.expiration_date and enrollment.expiration_date < current_time:
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
def get_certificate(
    course_id: str,
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        # Validate course_id format
        try:
            course_uuid = uuid.UUID(course_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid course ID format"
            )

        # Get course first
        course = session.exec(
            select(Course).where(Course.id == course_uuid)
        ).first()

        if not course:
            raise HTTPException(
                status_code=404,
                detail="Course not found"
            )

        # Check if course is completed
        course_progress = session.exec(
            select(CourseProgress).where(
                CourseProgress.user_id == user.id,
                CourseProgress.course_id == course_uuid,
                CourseProgress.completed == True
            )
        ).first()

        if not course_progress:
            raise HTTPException(
                status_code=403,
                detail="You must complete the course to get a certificate"
            )

        # Get certificate
        certificate = session.exec(
            select(Certificate).where(
                Certificate.user_id == user.id,
                Certificate.course_id == course_uuid
            )
        ).first()

        if not certificate:
            # Generate new certificate if it doesn't exist
            try:
                if not user.full_name:
                    raise HTTPException(status_code=400, detail="Full name is required to generate a certificate. Please complete your profile.")
                certificate_generator = CertificateGenerator()
                certificate_url = certificate_generator.generate(
                    username=user.full_name,
                    course_title=course.title,
                    completion_date=course_progress.completed_at
                )

                # Save certificate record
                certificate = Certificate(
                    user_id=user.id,
                    course_id=course_uuid,
                    file_path=certificate_url,
                    certificate_number=os.path.basename(certificate_url).split('/')[-1].replace('certificate_', '').replace('.pdf', '')
                )
                session.add(certificate)
                session.commit()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error generating certificate: {str(e)}"
                )

        # Return the B2 URL directly
        return {
            "certificate_url": certificate.file_path,
            "certificate_number": certificate.certificate_number
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving certificate: {str(e)}"
        )