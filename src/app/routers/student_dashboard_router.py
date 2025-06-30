from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from uuid import UUID
from datetime import datetime

from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..models.enrollment import Enrollment
from ..models.course import Course
from ..models.video import Video
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.quiz import Quiz, QuizSubmission
from ..models.video_progress import VideoProgress
from ..models.course_feedback import CourseFeedback
from ..models.course_progress import CourseProgress
from ..schemas.course_feedback import CourseFeedbackCreate

router = APIRouter()

def _get_analytics_for_course(course_id: UUID, user, db: Session):
    """Helper function to compute analytics for a single course for a given user."""
    # --- Enrollment check ---
    current_time = datetime.utcnow()
    enrollment = db.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_id,
            Enrollment.status == "approved",
            Enrollment.is_accessible == True,
            ((Enrollment.expiration_date > current_time) | (Enrollment.expiration_date == None))
        )
    ).first()
    if not enrollment:
        # This can happen if called for a course the user is not enrolled in.
        # Return None or raise an exception, depending on desired handling.
        return None

    # --- Course info ---
    course = db.exec(select(Course).where(Course.id == course_id)).first()
    if not course:
        return None # Course not found
    course_info = {"title": course.title, "description": course.description}

    # Videos
    total_videos = db.exec(select(Video).where(Video.course_id == course_id)).all()
    videos_watched = db.exec(
        select(VideoProgress).where(
            VideoProgress.video_id.in_(select(Video.id).where(Video.course_id == course_id)),
            VideoProgress.user_id == user.id,
            VideoProgress.completed == True
        )
    ).all()

    # Assignments
    total_assignments = db.exec(select(Assignment).where(Assignment.course_id == course_id)).all()
    assignments_submitted = db.exec(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id.in_(
                select(Assignment.id).where(Assignment.course_id == course_id)
            ),
            AssignmentSubmission.student_id == user.id
        )
    ).all()

    # Quizzes
    total_quizzes = db.exec(select(Quiz).where(Quiz.course_id == course_id)).all()
    quizzes_attempted = db.exec(
        select(QuizSubmission).where(
            QuizSubmission.quiz_id.in_(
                select(Quiz.id).where(Quiz.course_id == course_id)
            ),
            QuizSubmission.student_id == user.id
        )
    ).all()

    # Calculate progress percentage
    completed = len(videos_watched) + len(assignments_submitted) + len(quizzes_attempted)
    total = len(total_videos) + len(total_assignments) + len(total_quizzes)
    progress = int((completed / total) * 100) if total > 0 else 0

    # --- Update CourseProgress if 100% ---
    course_progress = db.exec(
        select(CourseProgress).where(
            CourseProgress.user_id == user.id,
            CourseProgress.course_id == course_id
        )
    ).first()
    now = datetime.utcnow()
    if progress == 100:
        if not course_progress or not course_progress.completed:
            if course_progress:
                course_progress.completed = True
                course_progress.completed_at = now
                course_progress.progress_percentage = 100.0
            else:
                course_progress = CourseProgress(
                    user_id=user.id, course_id=course_id, completed=True,
                    completed_at=now, progress_percentage=100.0
                )
            db.add(course_progress)
            db.commit()
    elif course_progress and course_progress.progress_percentage != progress:
        course_progress.progress_percentage = float(progress)
        db.add(course_progress)
        db.commit()

    return {
        "course_id": str(course_id),
        "course": course_info,
        "videos": {"total": len(total_videos), "watched": len(videos_watched)},
        "assignments": {"total": len(total_assignments), "submitted": len(assignments_submitted)},
        "quizzes": {"total": len(total_quizzes), "attempted": len(quizzes_attempted)},
        "progress": progress
    }

@router.get("/all-analytics")
def get_all_student_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Fetches analytics for all courses a student is enrolled in."""
    current_time = datetime.utcnow()
    enrollments = db.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "approved",
            Enrollment.is_accessible == True,
            ((Enrollment.expiration_date > current_time) | (Enrollment.expiration_date == None))
        )
    ).all()

    if not enrollments:
        return []

    all_analytics = []
    for enrollment in enrollments:
        analytics = _get_analytics_for_course(enrollment.course_id, user, db)
        if analytics:
            all_analytics.append(analytics)
    
    return all_analytics

@router.get("/courses/{course_id}/analytics")
def get_single_course_analytics(
    course_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Fetches analytics for a single course."""
    analytics = _get_analytics_for_course(course_id, user, db)
    if not analytics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics not found. You may not be enrolled or the course may not exist.")
    return analytics

@router.post("/courses/{course_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_course_feedback(
    course_id: UUID,
    payload: CourseFeedbackCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submits feedback for a completed course."""
    # Ensure user is enrolled and access is valid
    current_time = datetime.utcnow()
    enrollment = db.exec(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_id,
            Enrollment.status == "approved",
            Enrollment.is_accessible == True,
            ((Enrollment.expiration_date > current_time) | (Enrollment.expiration_date == None))
        )
    ).first()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must be enrolled in the course to submit feedback.")

    # Ensure course is completed by the user
    course_progress = db.exec(
        select(CourseProgress).where(
            CourseProgress.user_id == user.id,
            CourseProgress.course_id == course_id,
            CourseProgress.completed == True
        )
    ).first()
    if not course_progress:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must complete the course before submitting feedback.")

    feedback = CourseFeedback(
        user_id=user.id,
        course_id=course_id,
        feedback=payload.feedback,
        improvement_suggestions=payload.improvement_suggestions
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"detail": "Feedback submitted successfully."}
