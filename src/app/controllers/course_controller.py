# File: application/src/app/controllers/course_controller.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, or_
from sqlalchemy.orm import selectinload, joinedload
from src.app.models.course import Course
from src.app.models.video import Video
from src.app.models.quiz import Quiz, QuizSubmission, Question, Option
from src.app.schemas.video import VideoWithProgress, VideoCreate, VideoUpdate
from src.app.schemas.quiz import QuizRead, QuizSubmissionCreate, QuizSubmissionRead
from src.app.schemas.course import CourseRead, CourseListRead, CourseExploreList, CourseExploreDetail, CourseCurriculumDetail, CourseDetail, CurriculumSchema, OutcomesSchema, PrerequisitesSchema, CourseBasicDetail, DescriptionSchema, CourseProgress as CourseProgressSchema
from src.app.models.user import User
from ..models.enrollment import Enrollment
from ..models.video_progress import VideoProgress
from ..models.course_progress import CourseProgress
from ..models.certificate import Certificate
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


def get_next_available_video(course_id: uuid.UUID, user_id: uuid.UUID, session: Session) -> tuple[Optional[Video], bool]:
    """
    Find the next video that should be shown to the user based on their progress.
    Returns a tuple of (next_video, all_completed)
    """
    # Get all videos in order
    videos = session.exec(
        select(Video)
        .where(Video.course_id == course_id)
        .order_by(Video.created_at.asc())
        .options(selectinload(Video.quiz))
    ).all()
    
    if not videos:
        return None, False
        
    # Get all video progresses for the user
    video_progresses = {
        vp.video_id: vp 
        for vp in session.exec(
            select(VideoProgress)
            .where(
                VideoProgress.user_id == user_id,
                VideoProgress.video_id.in_([v.id for v in videos])
            )
        ).all()
    }
    
    # Get all quiz submissions for the user in this course
    quiz_submissions = {
        qs.quiz_id: qs
        for qs in session.exec(
            select(QuizSubmission)
            .where(
                QuizSubmission.student_id == user_id,
                QuizSubmission.quiz_id.in_([v.quiz_id for v in videos if v.quiz_id])
            )
        ).all()
    }
    
    # Find the first video that's not completed or whose quiz is not passed
    for i, video in enumerate(videos):
        progress = video_progresses.get(video.id)
        
        # If video has a quiz, check if it's passed
        if video.quiz_id:
            submission = quiz_submissions.get(video.quiz_id)
            quiz_passed = bool(submission and submission.score >= 0.7)  # Assuming 70% is passing
            
            # If quiz is not passed, this is the next video to show
            if not quiz_passed:
                return video, False
                
        # If no quiz or quiz passed, check if video is completed
        if not progress or not progress.completed:
            return video, False
            
    # All videos and quizzes completed
    return None, True

@router.get("/my-courses/{course_id}/videos-with-progress", response_model=list[VideoWithProgress])
def get_course_videos_with_progress(
    course_id: str,
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        course_uuid = uuid.UUID(course_id)
        
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == course_uuid,
                Enrollment.status == "approved"
            )
        ).first()

        if not enrollment or not enrollment.is_accessible:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this course."
            )

        # Get all videos for the course with their quizzes
        videos = session.exec(
            select(Video)
            .where(Video.course_id == course_uuid)
            .order_by(Video.created_at.asc())
            .options(joinedload(Video.quiz))  # Use joinedload instead of selectinload
        ).unique().all()  # Add unique() to avoid duplicate rows
        
        if not videos:
            return []
            
        # Get all video progresses for the user
        video_progresses = {
            vp.video_id: vp 
            for vp in session.exec(
                select(VideoProgress)
                .where(
                    VideoProgress.user_id == user.id,
                    VideoProgress.video_id.in_([v.id for v in videos])
                )
            ).all()
        }
        
        # Get all quiz submissions for the user in this course
        quiz_submissions = {
            qs.quiz_id: qs
            for qs in session.exec(
                select(QuizSubmission)
                .where(
                    QuizSubmission.student_id == user.id,
                    QuizSubmission.quiz_id.in_([v.quiz_id for v in videos if v.quiz_id])
                )
            ).all()
        }
        
        # Find the next available video
        next_video, all_completed = get_next_available_video(course_uuid, user.id, session)
        
        # Prepare the response
        result = []
        for i, video in enumerate(videos):
            progress = video_progresses.get(video.id)
            quiz = None
            quiz_passed = False
            
            # Get quiz info if exists
            quiz_data = None
            quiz_passed = False
            
            if video.quiz_id:
                # Make sure we have the quiz data
                if not hasattr(video, 'quiz') or not video.quiz:
                    video.quiz = session.get(Quiz, video.quiz_id)
                
                if video.quiz:
                    quiz_data = video.quiz
                    submission = quiz_submissions.get(video.quiz_id)
                    quiz_passed = bool(submission and submission.score >= 0.7)  # 70% passing score
            
            # Determine if this video is accessible
            is_accessible = True
            required_quiz_passed = True
            previous_quiz_passed = True
            
            # If there's a previous video with a quiz, check if it was passed
            if i > 0 and videos[i-1].quiz_id:
                prev_submission = quiz_submissions.get(videos[i-1].quiz_id)
                prev_quiz_passed = bool(prev_submission and prev_submission.score >= 0.7)
                required_quiz_passed = prev_quiz_passed
                previous_quiz_passed = prev_quiz_passed
                is_accessible = prev_quiz_passed
            
            # If this is the next available video, mark it as such
            is_next_available = next_video and video.id == next_video.id
            
            # If all videos are completed, the last video is the next available
            if all_completed and i == len(videos) - 1:
                is_next_available = True
            
            # If this video is before the next available one, it's accessible
            if next_video and video.created_at < next_video.created_at:
                is_accessible = True
            
            # If this is the first video, it's always accessible
            if i == 0:
                is_accessible = True
                required_quiz_passed = True
            
            result.append(VideoWithProgress(
                id=video.id,
                course_id=video.course_id,
                cloudinary_url=video.cloudinary_url,
                title=video.title,
                description=video.description,
                duration=video.duration,
                is_preview=video.is_preview,
                quiz_id=video.quiz_id,
                quiz=quiz_data,
                watched=bool(progress and progress.completed),
                quiz_passed=quiz_passed,
                is_accessible=is_accessible,
                is_next_available=is_next_available,
                next_video_id=next_video.id if next_video and i < len(videos) - 1 else None,
                required_quiz_passed=required_quiz_passed,
                previous_quiz_passed=previous_quiz_passed
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