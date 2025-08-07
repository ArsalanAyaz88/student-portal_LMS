from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlmodel import Session, select, func
from sqlalchemy.orm import selectinload
from src.app.models.course import Course
from src.app.models.video import Video
from src.app.models.quiz import Quiz, QuizSubmission, Question
from src.app.schemas.quiz import QuizSubmissionRead, QuizSubmissionCreate
from src.app.schemas.course import (
    CourseRead, CourseExploreList, CourseExploreDetail,
    CurriculumSchema, OutcomesSchema, PrerequisitesSchema, DescriptionSchema,
    CourseProgress as CourseProgressSchema
)
from src.app.schemas.course import VideoWithCheckpoint
from src.app.models.user import User 
from src.app.models.enrollment import Enrollment
from src.app.models.enrollment_application import EnrollmentApplication
from src.app.models.video_progress import VideoProgress
from src.app.models.course_progress import CourseProgress
from src.app.models.certificate import Certificate
from src.app.db.session import get_db
from src.app.utils.dependencies import get_current_user
from src.app.utils.certificate_generator import CertificateGenerator
from src.app.utils.time import get_pakistan_time
import uuid
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
import logging
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from urllib.parse import urlparse
import traceback
from ..config.s3_config import s3_client, S3_BUCKET_NAME

def to_hls_url(original_url: str) -> str:
    """Converts a standard Cloudinary video URL to an HLS streaming URL."""
    if not original_url or 'res.cloudinary.com' not in original_url:
        return original_url

    # The public_id is part of the URL. We can derive the HLS URL by replacing
    # the format extension with .m3u8 and adding a streaming profile.
    # Example:
    # From: https://res.cloudinary.com/demo/video/upload/v1589232929/dog.mp4
    # To:   https://res.cloudinary.com/demo/video/upload/sp_hd/v1589232929/dog.m3u8

    parts = original_url.split('/upload/')
    if len(parts) != 2:
        return original_url

    base_url, version_and_public_id = parts
    # Remove the existing format for a clean slate
    public_id_with_format = version_and_public_id.split('/')[-1]
    public_id = os.path.splitext(public_id_with_format)[0]

    # Reconstruct the path without the final filename part
    path_parts = version_and_public_id.split('/')[:-1]
    path_parts.append(public_id)
    version_and_public_id_no_ext = "/".join(path_parts)

    # Using a generic adaptive bitrate streaming profile 'sp_auto'
    hls_url = f"{base_url}/upload/sp_auto/{version_and_public_id_no_ext}.m3u8"
    
    return hls_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from datetime import datetime

router = APIRouter(tags=["Courses"])


@router.get("/my-courses", response_model=list[CourseRead])
def get_my_courses(user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    # Find all enrollments for the user that are approved and accessible
    enrollments = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "approved"
        )
    ).all()
    
    # Filter enrollments based on expiration and create a map
    valid_enrollment_map = {}
    for enrollment in enrollments:
        enrollment.update_expiration_status()
        if enrollment.is_accessible:
            valid_enrollment_map[enrollment.course_id] = enrollment.expiration_date
            
    if not valid_enrollment_map:
        return []
    
    course_ids = list(valid_enrollment_map.keys())
    
    courses = session.exec(select(Course).where(Course.id.in_(course_ids))).all()
    
    response_courses = []
    for course in courses:
        thumbnail_url = course.thumbnail_url
        if thumbnail_url and 's3.amazonaws.com' in thumbnail_url:
            try:
                key = urlparse(thumbnail_url).path.lstrip('/')
                thumbnail_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET_NAME, 'Key': key},
                    ExpiresIn=3600
                )
            except Exception as e:
                logger.error(f"Error generating presigned URL for my-courses {course.id}: {e}")
                thumbnail_url = None # Or a placeholder URL

        response_courses.append(
            CourseRead(
                id=course.id,
                title=course.title,
                thumbnail_url=thumbnail_url,
                expiration_date=valid_enrollment_map.get(course.id)
            )
        )
    return response_courses


@router.get("/explore-courses", response_model=list[CourseExploreList])
def explore_courses(session: Session = Depends(get_db)):
    logger.info("Request received for explore-courses")
    try:
        courses = session.exec(select(Course)).all()
        logger.info(f"Found {len(courses)} courses to explore.")
        
        response_courses = []
        for course in courses:
            thumbnail_url = course.thumbnail_url
            logger.info(f"Processing course '{course.title}' (ID: {course.id}). Original thumbnail: {thumbnail_url}")

            parsed_url = urlparse(thumbnail_url)
            if thumbnail_url and 'amazonaws.com' in parsed_url.netloc:
                logger.info(f"Course ID {course.id}: URL is from S3. Attempting to generate presigned URL.")
                try:
                    key = urlparse(thumbnail_url).path.lstrip('/')
                    if not key:
                        logger.warning(f"Course ID {course.id}: Could not parse a valid key from S3 URL: {thumbnail_url}")
                        thumbnail_url = None
                    else:
                        thumbnail_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': S3_BUCKET_NAME, 'Key': key},
                            ExpiresIn=3600
                        )
                        logger.info(f"Course ID {course.id}: Successfully generated presigned URL.")
                except Exception as e:
                    logger.error(f"Course ID {course.id}: Error generating presigned URL: {e}", exc_info=True)
                    thumbnail_url = None
            elif thumbnail_url:
                logger.info(f"Course ID {course.id}: URL is not from S3, returning it directly.")
            else:
                logger.info(f"Course ID {course.id}: Has no thumbnail URL.")

            response_courses.append(
                CourseExploreList(
                    id=course.id,
                    title=course.title,
                    price=course.price,
                    thumbnail_url=thumbnail_url
                )
            )
        logger.info("Finished processing all courses for explore-courses.")
        return response_courses
    except Exception as e:
        logger.exception(f"An unexpected error occurred in explore_courses: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching courses.")


@router.get("/{course_id}/thumbnail-url", response_model=dict)
def get_course_thumbnail_url(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user) 
): 
    logger.info(f"Request received for thumbnail, course_id: {course_id}")
    try:
        course = db.get(Course, course_id)
        if not course:
            logger.warning(f"Course with id {course_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        if not course.thumbnail_url:
            logger.warning(f"Course {course_id} found, but it has no thumbnail_url.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not available")

        logger.info(f"Course {course_id} found with thumbnail_url: {course.thumbnail_url}")

        # Ensure it's an S3 URL before attempting to generate a pre-signed URL
        if 's3.amazonaws.com' not in course.thumbnail_url:
            logger.info(f"URL for course {course_id} is not an S3 URL. Returning it directly.")
            return {"thumbnail_url": course.thumbnail_url}

        key = urlparse(course.thumbnail_url).path.lstrip('/')
        logger.info(f"Extracted S3 key for course {course_id}: {key}")

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': key},
            ExpiresIn=3600
        )
        logger.info(f"Successfully generated pre-signed URL for course {course_id}")
        return {"thumbnail_url": presigned_url}

    except HTTPException as http_exc:
        # Re-raise HTTPException to ensure FastAPI handles it correctly
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred while generating thumbnail URL for course {course_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/explore-courses/{course_id}", response_model=CourseExploreDetail)
def explore_course_detail(course_id: str, session: Session = Depends(get_db)):
    logger.info(f"Fetching course detail for course_id: {course_id}")
    try:
        try:
            course_uuid = uuid.UUID(course_id)
        except ValueError:
            logger.warning(f"Invalid UUID format for course_id: {course_id}")
            raise HTTPException(status_code=400, detail="Invalid course ID format")

        course = session.exec(
            select(Course).options(
                selectinload(Course.videos),
                selectinload(Course.quizzes)
            ).where(Course.id == course_uuid)
        ).first()

        if not course:
            logger.warning(f"Course not found for course_id: {course_id}")
            raise HTTPException(status_code=404, detail="Course not found")
        
        logger.info(f"Course found: {course.title}")

        instructor_name = "Dr Sabir ALi Butt"

        sections = [
            {
                "id": "main-section",
                "title": "Course Content",
                "videos": course.videos,
                "quizzes": course.quizzes
            }
        ]

        thumbnail_url = course.thumbnail_url
        logger.info(f"Original thumbnail URL from DB for course {course.id}: {thumbnail_url}")

        parsed_url = urlparse(thumbnail_url)
        if thumbnail_url and 'amazonaws.com' in parsed_url.netloc:
            logger.info(f"URL is from S3. Attempting to generate presigned URL.")
            try:
                key = urlparse(thumbnail_url).path.lstrip('/')
                if not key:
                    logger.warning(f"Could not parse a valid key from S3 URL: {thumbnail_url}")
                    thumbnail_url = None
                else:
                    thumbnail_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': S3_BUCKET_NAME, 'Key': key},
                        ExpiresIn=3600
                    )
                    logger.info(f"Successfully generated presigned URL for course {course.id}")
            except Exception as e:
                logger.error(f"Error generating presigned URL for course detail {course.id}: {e}", exc_info=True)
                thumbnail_url = None
        elif thumbnail_url:
            logger.info(f"URL is not from S3, returning it directly: {thumbnail_url}")
        else:
            logger.info(f"Course {course.id} has no thumbnail URL.")

        response_data = CourseExploreDetail(
            id=course.id,
            title=course.title,
            description=course.description or "",
            price=course.price,
            instructor_name=instructor_name,
            image_url=thumbnail_url or "",
            sections=sections
        )
        logger.info(f"Returning final image_url to frontend: {response_data.image_url}")
        return response_data

    except HTTPException as http_exc:
        logger.error(f"HTTPException in explore_course_detail for {course_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error fetching course detail for {course_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching course details.")


@router.get("/my-courses/{course_id}/enrollment-status", response_model=dict)
def get_enrollment_status(course_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    # 1. Check for an approved enrollment first
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_uuid,
            Enrollment.status == "approved"
        )
    ).first()

    if enrollment:
        return {"status": "APPROVED"}

    # 2. If not enrolled, check for a pending or rejected application
    application = session.exec(
        select(EnrollmentApplication).where(
            EnrollmentApplication.user_id == user.id,
            EnrollmentApplication.course_id == course_uuid
        )
    ).first()

    if application:
        return {"status": application.status.upper()}

    # 3. If no enrollment or application exists, the user has not applied
    return {"status": "NOT_APPLIED"}


@router.get("/{course_id}/curriculum", response_model=CurriculumSchema)
def get_course_curriculum(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CurriculumSchema(curriculum=course.curriculum or "")


@router.get("/{course_id}/outcomes", response_model=OutcomesSchema)
def get_course_outcomes(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return OutcomesSchema(outcomes=course.outcomes or "")


@router.get("/{course_id}/prerequisites", response_model=PrerequisitesSchema)
def get_course_prerequisites(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return PrerequisitesSchema(prerequisites=course.prerequisites or "")


@router.get("/{course_id}/description", response_model=DescriptionSchema)
def get_course_description(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return DescriptionSchema(description=course.description or "")


@router.get("/my-courses/{course_id}/videos-with-checkpoint", response_model=list[VideoWithCheckpoint])
def get_course_videos_with_checkpoint(
    course_id: uuid.UUID,  
    user=Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        # No need to convert course_id as it's already a UUID object
        course_uuid = course_id
        
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
                cloudinary_url=to_hls_url(video.cloudinary_url),
                title=video.title,
                description=video.description,
                watched=progress_map.get(str(video.id), False)
            ))
        return result

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

        # Check enrollment and expiration
        current_time = datetime.utcnow()
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == video.course_id,
                Enrollment.status == "approved",
                Enrollment.is_accessible == True,
                (Enrollment.expiration_date > current_time) | (Enrollment.expiration_date == None)
            )
        ).first()

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="You are not enrolled in this course or your access has expired"
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

        try:
            session.commit()
        except Exception as commit_error:
            session.rollback()
            logger.error(f"Commit error in mark_video_completed: {str(commit_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error while saving video progress: {str(commit_error)}"
            )
        # Refresh the object to get the updated state if needed, though for just returning a message it's not strictly necessary
        # session.refresh(progress)
        return {"detail": message}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error in mark_video_completed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing video completion status: {str(e)}"
        )

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


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmissionRead)
def submit_quiz(
    quiz_id: uuid.UUID,
    submission: QuizSubmissionCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Check for previous submission
    existing_submission = session.exec(
        select(QuizSubmission).where(
            QuizSubmission.quiz_id == quiz_id, 
            QuizSubmission.student_id == user.id
        )
    ).first()

    if existing_submission:
        raise HTTPException(status_code=400, detail="You have already submitted this quiz.")

    total_questions = len(quiz.questions)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="This quiz has no questions.")

    correct_answers = 0
    for answer in submission.answers:
        question = session.get(Question, answer.question_id)
        if not question or question.quiz_id != quiz_id:
            continue # or raise HTTPException for invalid question_id

        correct_option = next((opt for opt in question.options if opt.is_correct), None)
        if correct_option and correct_option.id == answer.option_id:
            correct_answers += 1

    score = (correct_answers / total_questions) * 100
    passed = score >= 70  # Passing score threshold

    new_submission = QuizSubmission(
        quiz_id=quiz_id,
        student_id=user.id,
        score=score,
        passed=passed,
        answers_data=submission.dict() # Storing the submission for review
    )

    session.add(new_submission)
    session.commit()
    session.refresh(new_submission)

    return new_submission
@router.get("/courses/{course_id}/certificate")
async def get_certificate(
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
                certificate_url = await certificate_generator.generate(
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