# Standard Library Imports
import os
import re
import time
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
import traceback

# Third-party Imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

# Application-specific Imports
from src.app.db.session import get_db
from src.app.utils.dependencies import get_current_admin_user, get_current_user
from src.app.utils.email import send_application_approved_email, send_enrollment_rejected_email
from src.app.utils.file import save_upload_and_get_url
from src.app.utils.time import get_pakistan_time
from src.app.config.s3_config import s3_client, S3_BUCKET_NAME

# Models
from src.app.models.assignment import Assignment, AssignmentSubmission
from src.app.models.course import Course
from src.app.models.course_progress import CourseProgress
from src.app.models.enrollment import Enrollment
from src.app.models.enrollment_application import EnrollmentApplication, ApplicationStatus
from src.app.models.notification import Notification
from src.app.models.quiz import Quiz, Question, Option
from src.app.models.user import User
from src.app.models.video import Video
from src.app.models.video_progress import VideoProgress

# Schemas
from src.app.schemas.assignment import (
    AssignmentCreate, AssignmentUpdate, AssignmentRead, AssignmentList,
    SubmissionRead, SubmissionGrade, SubmissionStudent, SubmissionStudentsResponse
)
from src.app.schemas.course import (
    AdminCourseDetail, AdminCourseStats,
    CourseCreate, CourseUpdate, CourseRead, CourseCreateAdmin
)
from src.app.schemas.enrollment_application_schema import EnrollmentApplicationRead, EnrollmentApplicationUpdate
from src.app.schemas.notification import NotificationRead, AdminNotificationRead
from src.app.schemas.quiz import QuizCreate, QuizReadWithDetails, QuizRead, QuizCreateForVideo
from src.app.schemas.user import UserRead
from src.app.schemas.video import VideoAdminRead, VideoCreate, VideoRead, VideoUpdate

router = APIRouter()

# ─── AWS S3 Upload Signature ────────────────────────────────────────────────────────────────

@router.post("/create-upload-signature")
def create_upload_signature(folder: str = Form("videos")):
    logging.info(f"Creating AWS S3 upload signature for folder: {folder}")
    """
    Generate a pre-signed URL for direct AWS S3 upload.
    """
    try:
        if s3_client is None:
            raise HTTPException(status_code=500, detail="S3 client is not configured")
        
        # Generate a unique key for the file
        timestamp = int(time.time())
        file_key = f"{folder}/{timestamp}_{uuid.uuid4().hex}"
        
        # Generate pre-signed URL for PUT operation (upload)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': file_key,
                'ContentType': request_data.content_type,
                'ACL': 'public-read'
            },
            ExpiresIn=3600  # 1 hour
        )

        logging.info(f"Generated presigned URL: {presigned_url}")

        return {
            "presigned_url": presigned_url,
            "file_key": file_key,
            "bucket": S3_BUCKET_NAME,
            "folder": folder,
            "expires_in": 7200
        }
    except Exception as e:
        logging.error(f"Error creating S3 upload signature: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create upload signature.")

# 1. Enrollment Management
@router.get("/users", response_model=List[UserRead])
def list_students(session: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    query = select(User).where(User.role == "student")
    return session.exec(query).all()



@router.post("/upload/image", response_model=dict)
async def upload_image(
    file: UploadFile = File(...), 
    admin: User = Depends(get_current_admin_user)
):
    """
    Uploads an image to AWS S3 and returns the URL.
    This endpoint requires admin authentication.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only images are allowed."
        )
    
    try:
        image_url = await save_upload_and_get_url(file=file, folder="course_thumbnails")
        return {"url": image_url}
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading the image: {str(e)}"
        )



@router.post("/courses", status_code=status.HTTP_201_CREATED, response_model=AdminCourseDetail)
async def create_course(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    thumbnail_url: Optional[str] = Form(None),
    difficulty_level: Optional[str] = Form(None),
    outcomes: Optional[str] = Form(None),
    prerequisites: Optional[str] = Form(None),
    curriculum: Optional[str] = Form(None),
    status: str = Form("active"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create a new course.

    Note: Videos should be uploaded separately using the /api/v1/courses/{course_id}/videos endpoint.
    """
    logging.info(f"--- Creating new course: {title} ---")
    logging.info(f"Received form data - Title: {title}, Price: {price}, Thumbnail URL: {thumbnail_url}")
    try:
        # Ensure the admin user is in the current session
        session_admin = db.get(User, admin.id)
        if not session_admin:
            raise HTTPException(status_code=404, detail="Admin user not found in session")

        # Create the course instance
        course = Course(
            title=title,
            description=description,
            price=price,
            thumbnail_url=thumbnail_url,
            difficulty_level=difficulty_level,
            outcomes=outcomes,
            prerequisites=prerequisites,
            curriculum=curriculum,
            status=status,
            created_by=admin.id,
            updated_by=admin.id
        )

        db.add(course)
        db.commit()
        db.refresh(course)
        return course

    except Exception as e:
        db.rollback()
        # Log the full error for debugging
        logging.error(f"Error creating course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred on the server: {str(e)}"
        )


class SignatureRequest(BaseModel):
    content_type: str
    file_name: str

@router.post("/generate-video-upload-signature", response_model=dict)
async def generate_video_upload_signature(
    request_data: SignatureRequest,
    admin: User = Depends(get_current_admin_user)
):
    """
    Generates a pre-signed URL for a direct video upload to AWS S3, 
    using the Content-Type provided by the client.
    """
    logging.info(f"--- Generating video upload signature for content_type: {request_data.content_type} ---")
    try:
        if s3_client is None:
            logging.error("S3 client is not configured. Make sure AWS credentials and region are set.")
            raise HTTPException(status_code=500, detail="S3 client is not configured")

        content_type = request_data.content_type
        if not content_type.startswith('video/'):
            logging.warning(f"Invalid content type received: {content_type}")
            raise HTTPException(status_code=400, detail="Invalid content type. Only video files are allowed.")

        # Generate a unique key for the video file
        timestamp = int(time.time())
        file_key = f"videos/{timestamp}_{uuid.uuid4().hex}"
        logging.info(f"Generated S3 file key: {file_key}")

        # Generate pre-signed URL for PUT operation (upload)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': file_key,
                'ContentType': content_type
            },
            ExpiresIn=7200  # URL expires in 2 hours
        )
        
        logging.info(f"Successfully generated pre-signed URL for {file_key}")
        return {
            "presigned_url": presigned_url,
            "file_key": file_key,
            "bucket": S3_BUCKET_NAME,
            "expires_in": 7200
        }
    except Exception as e:
        tb_str = traceback.format_exc()
        logging.error(f"Error generating video upload signature: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate upload signature: {e}"
        )

class VideoCreateAdmin(BaseModel):
    title: str
    description: Optional[str] = None
    is_preview: bool = False
    video_url: str
    file_key: str
    duration: float
    order: int

@router.post("/courses/{course_id}/videos", response_model=VideoRead)
async def upload_video_for_course(
    course_id: uuid.UUID,
    video_data: VideoCreateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Save video metadata for a specific course after the video has been uploaded to S3.
    """
    logging.info(f"Received request to create video for course {course_id}")
    logging.debug(f"Video creation payload: {video_data.model_dump_json()}")

    course = db.get(Course, course_id)
    if not course:
        logging.warning(f"Course with ID {course_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    try:
        new_video = Video(
            title=video_data.title,
            description=video_data.description,
            cloudinary_url=video_data.video_url, # Use S3 URL for this field
            public_id=video_data.file_key,      # Store S3 file key
            duration=video_data.duration,
            course_id=course_id,
            is_preview=video_data.is_preview,
            order=video_data.order
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
        logging.info(f"Successfully created video with ID {new_video.id} for course {course_id}")
        return new_video

    except Exception as e:
        db.rollback()
        logging.error(f"Error creating video for course {course_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating the video: {str(e)}"
        )





@router.post("/videos", response_model=VideoAdminRead, status_code=status.HTTP_201_CREATED)
def create_video(video: VideoCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    logging.info(f"Received request to create video for course {video.course_id}")
    logging.debug(f"Video creation payload: {video.model_dump_json()}")
    try:
        # Check if the course exists
        course = db.get(Course, video.course_id)
        if not course:
            logging.warning(f"Course with ID {video.course_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get the highest order for the current course and add 1
        max_order = db.exec(select(func.max(Video.order)).where(Video.course_id == video.course_id)).one_or_none()
        new_order = (max_order or 0) + 1

        video_data = video.model_dump()
        video_data['order'] = new_order
        db_video = Video(
            title=video.title,
            description=video.description,
            cloudinary_url=video.cloudinary_url, # Use the correct field name
            course_id=video.course_id,
            order=new_order
        )
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        logging.info(f"Successfully created video with ID {db_video.id} for course {video.course_id}")
        return db_video
    except Exception as e:
        logging.error(f"Error creating video for course {video.course_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the video.")


@router.get("/videos", response_model=List[VideoAdminRead])
def get_admin_videos_for_course(
    course_id: uuid.UUID = Query(..., description="The ID of the course to fetch videos for"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Get all videos for a specific course for the admin panel, ordered by the 'order' field.
    """
    # Ensure the course exists to avoid fetching videos for a non-existent course
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course with ID {course_id} not found")

    # Query videos for the given course_id, ordered by the 'order' field
    statement = select(Video).where(Video.course_id == course_id).order_by(Video.order)
    videos = db.exec(statement).all()
    
    return videos


@router.put("/videos/{video_id}", response_model=VideoRead)
def update_video(
    video_id: uuid.UUID,
    video_update: VideoUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    logging.info(f"Received request to update video {video_id}")
    logging.debug(f"Video update payload: {video_update.model_dump_json(exclude_unset=True)}")
    try:
        db_video = db.get(Video, video_id)
        if not db_video:
            logging.warning(f"Video with ID {video_id} not found for update.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

        video_data = video_update.model_dump(exclude_unset=True)
        for key, value in video_data.items():
            setattr(db_video, key, value)

        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        logging.info(f"Successfully updated video {video_id}")
        return db_video
    except Exception as e:
        logging.error(f"Error updating video {video_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while updating the video.")


@router.get("/courses", response_model=List[Course], tags=["Admin"])
def get_all_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Retrieve all courses with creator information for the admin panel.
    """
    try:
        logging.info(f"Fetching courses for admin panel. Skip: {skip}, Limit: {limit}")
        statement = select(Course).order_by(Course.created_at.desc()).offset(skip).limit(limit)
        courses = db.exec(statement).all()
        logging.info(f"Found {len(courses)} courses.")
        return courses
    except Exception as e:
        logging.error(f"Error fetching courses for admin panel: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching courses."
        )


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Delete a video from the database and the corresponding file from S3.
    """
    logging.info(f"[ADMIN] Attempting to delete video with ID: {video_id}")

    db_video = db.get(Video, video_id)
    if not db_video:
        logging.warning(f"[ADMIN] Video not found for deletion: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")

    s3_file_key = db_video.public_id  # Assuming public_id stores the S3 file key

    try:
        # Step 1: Delete the database record
        logging.info(f"[ADMIN] Deleting video from DB: {db_video.id} - {db_video.title}")
        db.delete(db_video)
        db.commit()
        logging.info(f"[ADMIN] Successfully deleted video from DB: {video_id}")

        # Step 2: Delete the file from S3
        if s3_file_key and s3_client:
            try:
                logging.info(f"[ADMIN] Deleting file from S3 with key: {s3_file_key}")
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_file_key)
                logging.info(f"[ADMIN] Successfully deleted file from S3: {s3_file_key}")
            except Exception as s3_error:
                # Log the S3 error but don't prevent the API from confirming DB deletion
                logging.error(f"[ADMIN] Failed to delete file from S3. Key: {s3_file_key}. Error: {s3_error}", exc_info=True)
                # Optionally, you could raise an exception or handle this case differently

        return

    except Exception as e:
        logging.error(f"[ADMIN] Unexpected error during video deletion process: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the video.")


@router.get("/videos/{video_id}/view-url", response_model=dict)
def get_video_view_url(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Generate a pre-signed URL for viewing a private video from S3.
    """
    logging.info(f"Request to generate view URL for video_id: {video_id}")
    
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.public_id: # public_id should store the S3 key
        logging.error(f"Video {video_id} does not have a file key (public_id) associated with it.")
        raise HTTPException(status_code=500, detail="Video file key not found.")

    try:
        if s3_client is None:
            logging.error("S3 client is not configured.")
            raise HTTPException(status_code=500, detail="S3 client is not configured")

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': video.public_id 
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        
        logging.info(f"Successfully generated view URL for video {video_id}")
        return {"view_url": presigned_url}

    except Exception as e:
        tb_str = traceback.format_exc()
        logging.error(f"Error generating video view URL for {video.public_id}: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate video view URL."
        )



# 2. Notifications
@router.get("/notifications", response_model=List[AdminNotificationRead])
def get_notifications(session: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """
    Get notifications for the admin, extracting course_id from the details string
    for easier processing on the frontend.
    """
    notifications = session.exec(select(Notification).order_by(Notification.timestamp.desc()).limit(50)).all()
    
    response_data = []
    # Regex to find a UUID in the details string
    uuid_regex = re.compile(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.I)

    for notif in notifications:
        # Use the course_id directly from the notification record
        course_id = notif.course_id

        response_data.append(
            AdminNotificationRead(
                id=notif.id,
                user_id=notif.user_id,
                event_type=notif.event_type,
                details=notif.details,
                timestamp=notif.timestamp,
                course_id=course_id
            )
        )
    return response_data

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Delete a notification by its ID."""
    logging.info(f"Attempting to delete notification {notification_id}")
    try:
        notification = db.get(Notification, notification_id)
        if not notification:
            logging.warning(f"Notification {notification_id} not found for deletion.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

        db.delete(notification)
        db.commit()
        logging.info(f"Successfully deleted notification {notification_id}")
        return
    except Exception as e:
        db.rollback()
        tb_str = traceback.format_exc()
        logging.error(f"Error deleting notification {notification_id}: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while deleting the notification: {e}"
        )

@router.get("/enrollment-applications", response_model=List[EnrollmentApplicationRead])
def get_enrollment_applications(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Get all enrollment applications, with user and course details.
    """
    try:
        logging.info("Attempting to fetch enrollment applications with user and course details.")
        applications = db.exec(
            select(EnrollmentApplication).options(
                selectinload(EnrollmentApplication.user),
                selectinload(EnrollmentApplication.course)
            ).order_by(EnrollmentApplication.id.desc())
        ).all()
        logging.info(f"Successfully fetched {len(applications)} enrollment applications.")
        return applications
    except Exception as e:
        tb_str = traceback.format_exc()
        logging.error(f"An unexpected error occurred while fetching enrollment applications: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please check the logs.")
    return applications


@router.put("/enrollment-applications/{application_id}/status", response_model=EnrollmentApplicationRead)
def update_enrollment_application_status(
    application_id: uuid.UUID,
    update_data: EnrollmentApplicationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Update the status of an enrollment application (approve or reject).
    If approved, create an enrollment record to grant course access.
    """
    application = db.get(EnrollmentApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Keep track of the old status to see if it's the final approval
    old_status = application.status
    application.status = update_data.status

    # If the application is being approved for the first time OR after payment verification
    if update_data.status == ApplicationStatus.APPROVED and old_status != ApplicationStatus.APPROVED:
        # Check if an enrollment already exists to avoid duplicates
        existing_enrollment = db.exec(
            select(Enrollment).where(
                Enrollment.user_id == application.user_id,
                Enrollment.course_id == application.course_id
            )
        ).first()

        if not existing_enrollment:
            # Create the final enrollment record, giving the student access
            new_enrollment = Enrollment(
                user_id=application.user_id,
                course_id=application.course_id,
                status="active",
                is_accessible=True,
                enroll_date=datetime.utcnow(),
                # Set an expiration date, e.g., 1 year from now
                expiration_date=datetime.utcnow() + timedelta(days=365)
            )
            db.add(new_enrollment)

    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.put("/courses/{course_id}", response_model=CourseRead)
async def update_course(
    request: Request,
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"--- Admin Course Update: START for course_id: {course_id} ---")

    try:
        # 2. Fetch existing course
        db_course = db.get(Course, course_id)
        if not db_course:
            logger.warning(f"Course with ID {course_id} not found.")
            raise HTTPException(status_code=404, detail="Course not found")
        logger.info(f"Found course '{db_course.title}' for update.")

        # 3. Parse form data
        form_data = await request.form()
        update_data = {key: value for key, value in form_data.items()}
        logger.info(f"Received form data for update: {update_data}")

        # 4. Update course fields
        for key, value in update_data.items():
            if hasattr(db_course, key):
                # Coerce price to float if present
                if key == 'price' and value is not None:
                    try:
                        setattr(db_course, key, float(value))
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert price '{value}' to float.")
                        # Skip if conversion fails, or handle as an error
                        continue 
                else:
                    setattr(db_course, key, value)
            else:
                logger.warning(f"Field '{key}' not found in Course model, skipping.")

        db_course.updated_at = get_pakistan_time()
        db_course.updated_by = admin.id

        # 5. Commit changes to the database
        db.add(db_course)
        db.commit()
        db.refresh(db_course)

        logger.info(f"Successfully updated course '{db_course.title}' (ID: {db_course.id})")
        return db_course

    except HTTPException as http_exc:
        # Re-raise FastAPI's HTTP exceptions directly
        logger.error(f"HTTP Exception in update_course: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error in update_course: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal server error occurred."
        )

# Delete a course (hard delete)
@router.delete("/courses/{course_id}", status_code=status.HTTP_200_OK)
def delete_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"--- Admin Course Deletion: START for course_id: {course_id} ---")

    try:
        # 2. Fetch the course
        course = db.get(Course, course_id)
        if not course:
            logger.warning(f"Course with ID {course_id} not found for deletion.")
            raise HTTPException(status_code=404, detail="Course not found")
        logger.info(f"Found course '{course.title}' for deletion.")

        # 3. Manually delete related entities to avoid constraint violations.
        # This is more explicit and safer than relying solely on cascades.

        # Delete related enrollments
        enrollments = db.exec(select(Enrollment).where(Enrollment.course_id == course.id)).all()
        if enrollments:
            logger.info(f"Deleting {len(enrollments)} associated enrollments.")
            for enrollment in enrollments:
                db.delete(enrollment)
        
        # Delete related videos
        videos = db.exec(select(Video).where(Video.course_id == course.id)).all()
        if videos:
            logger.info(f"Deleting {len(videos)} associated videos.")
            for video in videos:
                db.delete(video)

        # Delete related quizzes
        quizzes = db.exec(select(Quiz).where(Quiz.course_id == course.id)).all()
        if quizzes:
            logger.info(f"Deleting {len(quizzes)} associated quizzes.")
            for quiz in quizzes:
                db.delete(quiz)
        
        # Commit deletions of related entities before deleting the course itself
        db.commit()

        # 4. Delete the course itself
        logger.info(f"Proceeding to delete the course object.")
        db.delete(course)
        db.commit()

        logger.info(f"Successfully deleted course '{course.title}' (ID: {course.id}).")
        return {"detail": "Course deleted successfully"}

    except HTTPException as http_exc:
        logger.error(f"HTTP Exception in delete_course: {http_exc.detail}")
        db.rollback()
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error during course deletion: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected internal server error occurred: {str(e)}"
        )
@router.get("/dashboard/stats", response_model=dict)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get overall platform statistics for admin dashboard"""
    import logging
    logging.info("[ADMIN DASHBOARD] /dashboard/stats endpoint called by admin: %s", getattr(admin, 'email', str(admin)))
    try:
        # Get total courses
        total_courses = db.exec(select(func.count(Course.id))).one_or_none()
        total_courses = total_courses if total_courses is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Total courses: {total_courses}")
        # Get total enrollments
        total_enrollments = db.exec(select(func.count(Enrollment.id))).one_or_none()
        total_enrollments = total_enrollments if total_enrollments is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Total enrollments: {total_enrollments}")
        # Get active enrollments
        active_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(Enrollment.is_accessible == True)
        ).one_or_none()
        active_enrollments = active_enrollments if active_enrollments is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Active enrollments: {active_enrollments}")
        # Get total revenue
        total_revenue = db.exec(
            select(func.sum(Course.price))
            .join(Enrollment, Course.id == Enrollment.course_id)
            .where(Enrollment.status == "approved")
        ).one_or_none()
        total_revenue = total_revenue if total_revenue is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Total revenue: {total_revenue}")
        # Get completion rate
        completed_courses = db.exec(
            select(func.count(CourseProgress.id))
            .where(CourseProgress.completed == True)
        ).one_or_none()
        completed_courses = completed_courses if completed_courses is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Completed courses: {completed_courses}")
        completion_rate = (completed_courses / total_enrollments * 100) if total_enrollments > 0 else 0
        logging.info(f"[ADMIN DASHBOARD] Completion rate: {completion_rate}")
        # Get recent enrollments (last 30 days)
        thirty_days_ago = get_pakistan_time() - timedelta(days=30)
        recent_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(Enrollment.enroll_date >= thirty_days_ago)
        ).one_or_none()
        recent_enrollments = recent_enrollments if recent_enrollments is not None else 0
        logging.info(f"[ADMIN DASHBOARD] Recent enrollments (30d): {recent_enrollments}")
        result = {
            "total_courses": total_courses,
            "total_enrollments": total_enrollments,
            "active_enrollments": active_enrollments,
            "recent_enrollments": recent_enrollments,
            "total_revenue": round(total_revenue, 2),
            "completion_rate": round(completion_rate, 2),
            "last_updated": get_pakistan_time().isoformat()
        }
        logging.info(f"[ADMIN DASHBOARD] Returning stats: {result}")
        return result
    except Exception as e:
        import traceback
        logging.error(f"[ADMIN DASHBOARD] Error fetching dashboard stats: {e}", exc_info=True)
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching dashboard stats: {str(e)}"
        )

@router.get("/courses", response_model=List[Course], tags=["Admin"])
async def list_courses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by course status"),
    search: Optional[str] = Query(None, description="Search in course title"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """List all courses with pagination and filtering"""
    try:
        query = select(Course)
        
        if status:
            query = query.where(Course.status == status)
        if search:
            query = query.where(Course.title.ilike(f"%{search}%"))
            
        courses = db.exec(query.offset(skip).limit(limit)).all()
        
        result = []
        for course in courses:
            # Get enrollment stats
            total_enrollments = db.exec(
                select(func.count(Enrollment.id))
                .where(Enrollment.course_id == course.id)
            ).first()
            
            active_enrollments = db.exec(
                select(func.count(Enrollment.id))
                .where(
                    Enrollment.course_id == course.id,
                    Enrollment.status == "approved"
                )
            ).first()
            
            # Get average progress
            avg_progress = db.exec(
                select(func.avg(CourseProgress.progress_percentage))
                .where(CourseProgress.course_id == course.id)
            ).first() or 0
            
            result.append(AdminCourseList(
                id=course.id,
                title=course.title,
                price=course.price,
                total_enrollments=total_enrollments,
                active_enrollments=active_enrollments,
                average_progress=round(avg_progress, 2),
                status=course.status,
                created_at=course.created_at,
                updated_at=course.updated_at
            ))
            
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing courses: {str(e)}"
        )

@router.get("/courses/{course_id}", response_model=AdminCourseDetail)
async def get_course_detail(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get detailed information about a specific course"""
    try:
        course = db.exec(
            select(Course)
            .where(Course.id == course_id)
            .options(selectinload(Course.videos))
        ).first()
        
        if not course:
            raise HTTPException(
                status_code=404,
                detail="Course not found"
            )
            
        # Get course statistics
        total_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(Enrollment.course_id == course.id)
        ).first()
        
        active_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(
                Enrollment.course_id == course.id,
                Enrollment.status == "approved"
            )
        ).first()
        
        completed_enrollments = db.exec(
            select(func.count(CourseProgress.id))
            .where(
                CourseProgress.course_id == course.id,
                CourseProgress.completed == True
            )
        ).first()
        
        avg_progress = db.exec(
            select(func.avg(CourseProgress.progress_percentage))
            .where(CourseProgress.course_id == course.id)
        ).first() or 0
        
        total_revenue = db.exec(
            select(func.sum(Course.price))
            .join(Enrollment)
            .where(
                Enrollment.course_id == course.id,
                Enrollment.status == "approved"
            )
        ).first() or 0
        
        stats = AdminCourseStats(
            total_enrollments=total_enrollments,
            active_enrollments=active_enrollments,
            completed_enrollments=completed_enrollments,
            average_progress=round(avg_progress, 2),
            total_revenue=total_revenue,
            last_updated=datetime.utcnow()
        )
        

        
        # Prepare video data according to the VideoRead schema in course.py
        video_data = []
        for video in course.videos:
            video_dict = {
                'id': str(video.id),  # Convert UUID to string as expected by the schema
                'youtube_url': video.youtube_url,
                'title': video.title or "",
                'description': video.description or ""
            }
            video_data.append(VideoRead(**video_dict))
            
        return AdminCourseDetail(
            id=course.id,
            title=course.title,
            description=course.description or "",
            price=float(course.price or 0.0),
            thumbnail_url=course.thumbnail_url,
            difficulty_level=course.difficulty_level or "",
            created_by=course.created_by or "system",
            updated_by=course.updated_by or "system",
            created_at=course.created_at or datetime.utcnow(),
            updated_at=course.updated_at or datetime.utcnow(),
            status=course.status or "active",
            stats=stats,
            videos=video_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching course details: {str(e)}"
        )


@router.put("/enrollments/approve")
def approve_enrollment_by_user(
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    duration_months: int = Query(..., description="Duration of access in months"),
    session: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    enrollment = session.exec(select(Enrollment).where(Enrollment.user_id == user_id, Enrollment.course_id == course_id)).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Set enrollment status and access
    enrollment.status = "approved"
    enrollment.is_accessible = True
    
    # Set enrollment date if not set
    if not enrollment.enroll_date:
        enrollment.enroll_date = get_pakistan_time()
    
    # Calculate and set expiration date
    enrollment.expiration_date = enrollment.enroll_date + timedelta(days=30 * duration_months)
    enrollment.update_expiration_status()
    
    session.add(enrollment)
    session.commit()
    
    # Notify student with expiration date
    notif = Notification(
        user_id=enrollment.user_id,
        course_id=enrollment.course_id,
        event_type="enrollment_approved",
        details=f"Enrollment approved for course ID {enrollment.course_id}. Access granted until {enrollment.expiration_date.strftime('%Y-%m-%d %H:%M:%S %Z')} ({enrollment.days_remaining} days remaining)",
    ) 
    session.add(notif)
    session.commit()

    # --- Send enrollment approval email ---
    try:
        # Load relationships if not already loaded
        user = enrollment.user
        course = enrollment.course
        # Defensive fallback if relationships are not loaded
        if user is None:
            from app.models.user import User
            user = session.exec(select(User).where(User.id == enrollment.user_id)).first()
        if course is None:
            course = session.exec(select(Course).where(Course.id == enrollment.course_id)).first()
        if user and course:
            send_enrollment_approved_email(
                to_email=user.email,
                course_title=course.title,
                expiration_date=enrollment.expiration_date.strftime('%Y-%m-%d'),
                days_remaining=enrollment.days_remaining or 0
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send enrollment approval email: {e}")
    # --- End email logic ---

    return {
        "detail": "Enrollment approved and student now has access.",
        "expiration_date": enrollment.expiration_date,
        "days_remaining": enrollment.days_remaining
    }


@router.put("/enrollments/test-expiration")
def test_enrollment_expiration(
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    session: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Test endpoint to set an enrollments expiration date to today.

    Args:
        user_id (uuid.UUID): ID of the user whose enrollment will be updated
        course_id (uuid.UUID): ID of the course for the enrollment
        session (Session): Database session
        admin (User): Authenticated admin user

    Returns:
        dict: Status message and expiration date
    """
    enrollment = session.exec(select(Enrollment).where(Enrollment.user_id == user_id, Enrollment.course_id == course_id)).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Set expiration date to today in Pakistan time
    today = get_pakistan_time().replace(hour=0, minute=0, second=0, microsecond=0)
    enrollment.expiration_date = today
    enrollment.update_expiration_status()
    
    session.add(enrollment)
    session.commit()
    
    # Notify student about expiration
    notif = Notification(
        user_id=enrollment.user_id,
        course_id=enrollment.course_id,  # Add the required course_id field
        event_type="enrollment_expired",
        details=f"Your enrollment for course ID {enrollment.course_id} has expired today ({today.strftime('%Y-%m-%d %H:%M:%S %Z')})",
    ) 
    session.add(notif)
    session.commit()
    
    return {
        "detail": "Enrollment expiration date set to today",
        "expiration_date": enrollment.expiration_date
    }

@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assignment for a course",
)
def admin_create_assignment(
    course_id: uuid.UUID,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create a new assignment for a course."""
    # 1) Ensure course exists
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # 2) Create the assignment instance with all required fields
    assignment = Assignment(
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        course_id=course_id,
        status="pending"  # Set a default status
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # 3) Return a valid AssignmentRead object
    return AssignmentRead(
        id=assignment.id,
        course_id=assignment.course_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        status='pending',  # Default status for a newly created assignment
        course_title=course.title,
        submission=None
    )

@router.get("/courses/{course_id}/assignments", response_model=List[AssignmentRead])
def admin_list_assignments(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """List all assignments under a given course for the admin panel."""
    query = (
        select(Assignment)
        .where(Assignment.course_id == course_id)
        .options(selectinload(Assignment.course))
    )
    assignments = db.exec(query).all()

    return [
        AssignmentRead(
            id=a.id,
            course_id=a.course_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            status='pending',  # Admin view doesn't have student-specific status
            course_title=a.course.title if a.course else "N/A",
            submission=None
        )
        for a in assignments
    ]

@router.delete(
    "/courses/{course_id}/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an assignment",
)
def admin_delete_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Remove an assignment."""
    assign = db.get(Assignment, assignment_id)
    if not assign or assign.course_id != course_id:
        raise HTTPException(404, "Assignment not found")
    db.delete(assign)
    db.commit()
    return

@router.get(
    "/courses/{course_id}/assignments/{assignment_id}/submissions/students",
    response_model=SubmissionStudentsResponse,
)
def admin_list_on_time_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    logging.info(f"Fetching submissions for assignment {assignment_id} in course {course_id}")
    try:
        assignment_query = select(Assignment).where(Assignment.id == assignment_id).options(selectinload(Assignment.course))
        assignment = db.exec(assignment_query).first()

        if not assignment or str(assignment.course_id) != str(course_id):
            raise HTTPException(status_code=404, detail="Assignment not found")

        submissions_query = (
            select(AssignmentSubmission)
            .where(AssignmentSubmission.assignment_id == assignment_id)
            .options(selectinload(AssignmentSubmission.user))
        )
        submissions = db.exec(submissions_query).all()

        student_submissions = []
        for sub in submissions:
            if sub.user:
                student_submissions.append(
                    SubmissionStudent(
                        id=sub.id,
                        student_id=sub.user.id,
                        email=sub.user.email,
                        full_name=sub.user.full_name,
                        submitted_at=sub.submitted_at,
                        content_url=sub.content_url,
                        grade=sub.grade,
                        feedback=sub.feedback,
                    )
                )
            else:
                logging.warning(f"Submission {sub.id} is missing a user relationship.")

        assignment_read = AssignmentRead(
            id=assignment.id,
            course_id=assignment.course_id,
            title=assignment.title,
            description=assignment.description,
            due_date=assignment.due_date,
            status='pending',
            course_title=assignment.course.title if assignment.course else "N/A",
            submission=None
        )

        return SubmissionStudentsResponse(
            assignment=assignment_read,
            submissions=student_submissions,
        )
    except Exception as e:
        db.rollback()
        tb_str = traceback.format_exc()
        logging.error(f"Error fetching submissions for assignment {assignment_id}: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching submissions: {e}"
        )

@router.put(
    "/courses/{course_id}/assignments/{assignment_id}/submissions/{submission_id}/grade",
    response_model=SubmissionRead,
    summary="Grade a student's assignment submission",
)
def admin_grade_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: SubmissionGrade,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    # 1) Ensure assignment exists under this course
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found for this course"
        )

    # 2) Load the submission
    submission = db.get(AssignmentSubmission, submission_id)
    if not submission or submission.assignment_id != assignment_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # 3) Apply grade & feedback
    submission.grade = payload.grade
    submission.feedback = payload.feedback

    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 4) Return the updated submission
    return submission

@router.put("/courses/{course_id}/assignments/{assignment_id}", response_model=AssignmentRead)
def admin_update_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Update an assignment's title, description, and due date."""
    logging.info(f"Attempting to update assignment {assignment_id} for course {course_id}")
    try:
        # Eagerly load the course to access its title for the response
        query = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .options(selectinload(Assignment.course))
        )
        assignment = db.exec(query).first()

        if not assignment or str(assignment.course_id) != str(course_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this course.",
            )

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(assignment, key, value)

        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        logging.info(f"Successfully updated assignment {assignment_id}")

        # Manually construct the response to match the AssignmentRead schema
        return AssignmentRead(
            id=assignment.id,
            course_id=assignment.course_id,
            title=assignment.title,
            description=assignment.description,
            due_date=assignment.due_date,
            status='pending',  # Default status for admin view
            course_title=assignment.course.title if assignment.course else "N/A",
            submission=None
        )

    except Exception as e:
        db.rollback()
        tb_str = traceback.format_exc()
        logging.error(f"Error updating assignment {assignment_id}: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while updating the assignment: {e}"
        )

@router.get("/s3-signature")
def get_s3_signature(admin: User = Depends(get_current_admin_user)):
    """
    Generate a pre-signed URL for direct uploads to AWS S3.
    """
    try:
        if s3_client is None:
            raise HTTPException(status_code=500, detail="S3 client is not configured")
        
        folder = "lms_videos"
        timestamp = int(time.time())
        file_key = f"{folder}/{timestamp}_{uuid.uuid4().hex}"
        
        # Generate pre-signed URL for PUT operation (upload)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': file_key,
                'ContentType': 'video/mp4'  # Default content type for videos
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        
        return {
            "presigned_url": presigned_url,
            "file_key": file_key,
            "bucket": S3_BUCKET_NAME,
            "folder": folder,
            "expires_in": 3600
        }
    except Exception as e:
        logging.error(f"Error generating S3 signature: {e}")
        raise HTTPException(status_code=500, detail="Could not generate upload signature.")

@router.get("/videos/{video_id}/quiz", response_model=QuizReadWithDetails, name="get_quiz_for_video")
def get_quiz_for_video(video_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    logging.info(f"Attempting to fetch quiz for video_id: {video_id}")
    try:
        quiz = db.exec(
            select(Quiz)
            .where(Quiz.video_id == video_id)
            .options(
                selectinload(Quiz.questions)
                .selectinload(Question.options)
            )
        ).first()

        if not quiz:
            logging.warning(f"No quiz found for video_id: {video_id}. Returning 404.")
            raise HTTPException(status_code=404, detail="Quiz not found for this video")

        logging.info(f"Successfully found quiz {quiz.id} for video {video_id}")
        return quiz
    except HTTPException:
        raise  # Let FastAPI handle HTTPException (404, etc.) correctly
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching quiz for video {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.post("/videos/{video_id}/quiz", response_model=QuizReadWithDetails)
def upsert_quiz_for_video(
    video_id: uuid.UUID,
    quiz_data: QuizCreateForVideo,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    logging.info(f"Starting quiz upsert for video {video_id}.")
    logging.debug(f"Quiz payload: {quiz_data.model_dump_json()}")
    
    video = db.get(Video, video_id)
    if not video:
        logging.warning(f"Video with id {video_id} not found during quiz upsert.")
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        quiz = video.quiz

        if quiz:
            # UPDATE existing quiz
            logging.info(f"Updating existing quiz {quiz.id} for video {video_id}.")
            quiz.title = quiz_data.title
            quiz.description = quiz_data.description
            
            logging.info(f"Deleting old questions and options for quiz {quiz.id}.")
            for question in list(quiz.questions): # Use list to avoid issues with collection modification during iteration
                for option in list(question.options):
                    db.delete(option)
                db.delete(question)
            db.flush() # Apply deletions to the session

        else:
            # CREATE new quiz
            logging.info(f"Creating new quiz for video {video_id}.")
            quiz = Quiz(
                title=quiz_data.title,
                description=quiz_data.description,
                course_id=video.course_id,
                video_id=video.id
            )
            db.add(quiz)
            db.flush() # Flush to get the new quiz ID
            logging.info(f"New quiz {quiz.id} created and linked to video {video_id}.")

        # CREATE new questions and options
        logging.info(f"Creating new questions and options for quiz {quiz.id}.")
        for q_data in quiz_data.questions:
            question = Question(text=q_data.text, quiz_id=quiz.id)
            db.add(question)
            db.flush() # Flush to get the new question ID

            options_to_create = []
            for o_data in q_data.options:
                options_to_create.append(Option(text=o_data.text, is_correct=o_data.is_correct, question_id=question.id))
            db.add_all(options_to_create)

        db.commit()
        db.refresh(quiz) # Refresh to load all new nested objects
        logging.info(f"Successfully committed upsert for quiz {quiz.id} for video {video_id}.")
        return quiz

    except Exception as e:
        logging.error(f"Error during quiz upsert for video {video_id}: {e}", exc_info=True)
        db.rollback()
        logging.info(f"Database transaction rolled back for video {video_id}.")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while saving the quiz.")


    logging.info(f"Fetching quiz for video {video_id}")
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.quiz:
        raise HTTPException(status_code=404, detail="Quiz not found for this video.")

    # Eagerly load questions and options
    quiz = db.exec(
        select(Quiz)
        .where(Quiz.id == video.quiz_id)
        .options(selectinload(Quiz.questions).selectinload(Question.options))
    ).first()

    if not quiz:
        # This case should be rare if video.quiz_id is set
        raise HTTPException(status_code=404, detail="Quiz not found.")

    logging.info(f"Successfully fetched quiz {quiz.id} for video {video_id}")
    return quiz


# ... (rest of the code remains the same)
    # Eagerly load the relationships to return them in the response
    updated_quiz = db.exec(
        select(Quiz)
        .where(Quiz.id == quiz.id)
        .options(selectinload(Quiz.questions).selectinload(Question.options))
    ).one()

    return updated_quiz


@router.post("/admin/quizzes", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Create a new quiz, including its questions and options."""
    # Check if the associated video exists
    video = db.get(Video, quiz_data.video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    # Create the Quiz instance
    db_quiz = Quiz(
        title=quiz_data.title,
        description=quiz_data.description,
        video_id=quiz_data.video_id
    )

    # Create Question and Option instances from the nested data
    for question_data in quiz_data.questions:
        db_question = Question(text=question_data.text)
        for option_data in question_data.options:
            db_option = Option(text=option_data.text, is_correct=option_data.is_correct)
            db_question.options.append(db_option)
        db_quiz.questions.append(db_question)

    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz



    return application


@router.get("/debug-video-info", dependencies=[Depends(get_current_admin_user)])
def debug_video_info(db: Session = Depends(get_db)):
    logging.info("--- DEBUG: Fetching video info for working vs non-working videos ---")
    try:
        # Case 1: Working Video
        # Course: "introduction to programming", Video: "888888"
        working_course_title = "introduction to programming"
        working_video_title = "888888"
        
        working_video = db.exec(
            select(Video)
            .join(Course)
            .where(Course.title == working_course_title, Video.title == working_video_title)
        ).first()

        # Case 2: Non-Working Video
        # Course: "Programming with Arsal", Video: "wqerwqer"
        non_working_course_title = "Programming with Arsal"
        non_working_video_title = "wqerwqer"

        non_working_video = db.exec(
            select(Video)
            .join(Course)
            .where(Course.title == non_working_course_title, Video.title == non_working_video_title)
        ).first()

        response = {
            "working_video": video_to_dict(working_video) if working_video else None,
            "non_working_video": video_to_dict(non_working_video) if non_working_video else None,
        }
        logging.info(f"--- DEBUG: Successfully fetched video info: {response} ---")
        return response

    except Exception as e:
        logging.error(f"--- DEBUG: Error fetching debug video info: {e} ---", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def video_to_dict(video: Video):
    if not video:
        return None
    return {
        "id": str(video.id),
        "title": video.title,
        "video_url": video.video_url,
        "cloudinary_url": video.cloudinary_url,
        "file_key": video.file_key,
        "course_id": str(video.course_id),
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "updated_at": video.updated_at.isoformat() if video.updated_at else None,
    }
