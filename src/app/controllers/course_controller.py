from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlmodel import Session, select, func
from sqlalchemy.orm import selectinload
from src.app.models.course import Course
from src.app.models.video import Video
from src.app.models.quiz import Quiz, QuizSubmission, Question
from src.app.schemas.quiz import QuizSubmissionRead, QuizSubmissionCreate
from src.app.schemas.video import VideoWithProgress
from src.app.schemas.course import (
    CourseRead, CourseExploreList, CourseExploreDetail,
    CurriculumSchema, OutcomesSchema, PrerequisitesSchema, DescriptionSchema,
    CourseProgress as CourseProgressSchema
)
from src.app.models.user import User
from src.app.models.enrollment import Enrollment
from src.app.models.video_progress import VideoProgress
from src.app.models.certificate import Certificate
from src.app.db.session import get_db
from src.app.utils.dependencies import get_current_user
from src.app.utils.certificate_generator import CertificateGenerator
from src.app.utils.time import get_pakistan_time
import uuid
import cloudinary.uploader
from fastapi.logger import logger
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
    
    return [
        CourseRead(
            id=course.id,
            title=course.title,
            thumbnail_url=course.thumbnail_url,
            expiration_date=valid_enrollment_map.get(course.id)
        ) for course in courses
    ]


@router.get("/explore-courses", response_model=list[CourseExploreList])
def explore_courses(session: Session = Depends(get_db)):
    courses = session.exec(select(Course)).all()
    return [
        CourseExploreList(
            id=course.id,
            title=course.title,
            price=course.price,
            thumbnail_url=course.thumbnail_url
        ) for course in courses
    ]


@router.get("/explore-courses/{course_id}", response_model=CourseExploreDetail)
def explore_course_detail(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    course = session.exec(
        select(Course).options(
            selectinload(Course.sections).options(
                selectinload(Section.videos),
                selectinload(Section.quizzes)
            )
        ).where(Course.id == course_uuid)
    ).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # The instructor's name needs to be fetched from the related User model
    instructor_name = course.instructor.name if course.instructor else "N/A"

    return CourseExploreDetail(
        id=course.id,
        title=course.title,
        description=course.description or "",
        price=course.price,
        instructor_name=instructor_name,
        image_url=course.thumbnail_url or "",
        sections=course.sections
    )


@router.get("/my-courses/{course_id}/enrollment-status", response_model=dict)
def get_enrollment_status(course_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)):
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


@router.get("/courses/{course_id}/curriculum", response_model=CurriculumSchema)
def get_course_curriculum(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CurriculumSchema(curriculum=course.curriculum or "")


@router.get("/courses/{course_id}/outcomes", response_model=OutcomesSchema)
def get_course_outcomes(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return OutcomesSchema(outcomes=course.outcomes or "")


@router.get("/courses/{course_id}/prerequisites", response_model=PrerequisitesSchema)
def get_course_prerequisites(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return PrerequisitesSchema(prerequisites=course.prerequisites or "")


@router.get("/courses/{course_id}/description", response_model=DescriptionSchema)
def get_course_description(course_id: str, session: Session = Depends(get_db)):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")
    course = session.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return DescriptionSchema(description=course.description or "")


@router.get("/my-courses/{course_id}/videos-with-progress", response_model=list[VideoWithProgress])
def get_course_videos_with_progress(
    course_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    # Check if the user is enrolled and approved
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_uuid,
            Enrollment.status == "approved"
        )
    ).first()

    if not enrollment:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course.")

    # Get all videos for the course, ordered by the 'order' field
    videos = session.exec(
        select(Video).where(Video.course_id == course_uuid).order_by(Video.order)
    ).all()

    if not videos:
        return []

    # Get all of the user's progress for this course in one go
    progress_records = session.exec(
        select(VideoProgress).where(
            VideoProgress.user_id == user.id,
            VideoProgress.video_id.in_([v.id for v in videos])
        )
    ).all()
    watched_video_ids = {p.video_id for p in progress_records}

    # Get all of the user's quiz submissions for this course
    quiz_submissions = session.exec(
        select(QuizSubmission).where(
            QuizSubmission.user_id == user.id,
            QuizSubmission.quiz_id.in_([v.quiz_id for v in videos if v.quiz_id])
        )
    ).all()
    passed_quiz_ids = {s.quiz_id for s in quiz_submissions if s.passed}

    response_videos = []
    previous_video_unlocked = True  # The first video is always accessible

    for video in videos:
        is_accessible = False
        if previous_video_unlocked:
            is_accessible = True

        watched = video.id in watched_video_ids
        quiz_passed = video.quiz_id in passed_quiz_ids if video.quiz_id else True

        # Determine if the next video should be unlocked
        previous_video_unlocked = is_accessible and watched and quiz_passed

        quiz_status = 'not_taken'
        if video.quiz_id:
            if video.quiz_id in passed_quiz_ids:
                quiz_status = 'passed'
            # Check if there is any submission, to mark as 'failed'
            elif any(s.quiz_id == video.quiz_id for s in quiz_submissions):
                quiz_status = 'failed'

        response_videos.append(
            VideoWithProgress(
                id=video.id,
                title=video.title,
                description=video.description,
                url=video.video_url, # Assuming url is the field name in VideoWithProgress
                duration=video.duration,
                order=video.order,
                is_preview=video.is_preview,
                course_id=video.course_id,
                quiz_id=video.quiz_id,
                watched=watched,
                quiz_status=quiz_status,
                is_accessible=is_accessible
            )
        )

    return response_videos


@router.post("/videos/{video_id}/complete", status_code=status.HTTP_200_OK)
def toggle_video_completion(
    video_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        try:
            video_uuid = uuid.UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid video ID format.")

        video = session.get(Video, video_uuid)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found.")

        enrollment = session.exec(
            select(Enrollment).where(Enrollment.course_id == video.course_id, Enrollment.student_id == user.id)
        ).first()

        if not enrollment:
            raise HTTPException(status_code=403, detail="You are not enrolled in this course.")

        if enrollment.access_expires_on and enrollment.access_expires_on < get_pakistan_time().date():
            raise HTTPException(status_code=403, detail="Your access to this course has expired.")

        progress = session.exec(
            select(VideoProgress).where(VideoProgress.video_id == video_uuid, VideoProgress.user_id == user.id)
        ).first()

        if progress:
            progress.is_completed = not progress.is_completed
            status_message = "completed" if progress.is_completed else "incomplete"
        else:
            progress = VideoProgress(video_id=video_uuid, user_id=user.id, is_completed=True)
            session.add(progress)
            status_message = "completed"

        session.commit()
        session.refresh(progress)

        # Update course progress
        completed_videos_count = session.exec(
            select(func.count(VideoProgress.id))
            .join(Video, Video.id == VideoProgress.video_id)
            .where(Video.course_id == video.course_id, VideoProgress.user_id == user.id, VideoProgress.is_completed == True)
        ).one()

        total_videos_count = session.exec(
            select(func.count(Video.id)).where(Video.course_id == video.course_id)
        ).one()

        course_progress = session.exec(
            select(CourseProgress).where(CourseProgress.course_id == video.course_id, CourseProgress.user_id == user.id)
        ).first()

        if not course_progress:
            course_progress = CourseProgress(course_id=video.course_id, user_id=user.id)
            session.add(course_progress)

        course_progress.completion_percentage = (completed_videos_count / total_videos_count) * 100 if total_videos_count > 0 else 0
        course_progress.last_updated = get_pakistan_time()

        session.commit()

        return {"message": f"Video marked as {status_message}", "is_completed": progress.is_completed}

    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in toggle_video_completion: {e}")
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
            QuizSubmission.user_id == user.id
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
        user_id=user.id,
        score=score,
        passed=passed,
        answers_data=submission.dict() # Storing the submission for review
    )

    session.add(new_submission)
    session.commit()
    session.refresh(new_submission)

    return new_submission