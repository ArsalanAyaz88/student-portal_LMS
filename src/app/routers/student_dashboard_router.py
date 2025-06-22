from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from uuid import UUID

from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..models.video import Video
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.quiz import Quiz, QuizSubmission
from ..models.video_progress import VideoProgress
from ..models.course_feedback import CourseFeedback
from ..models.course_progress import CourseProgress
from ..schemas.course_feedback import CourseFeedbackCreate
from fastapi import HTTPException, status

router = APIRouter(
    prefix="/courses/{course_id}/analytics",
    tags=["student_analytics"],
)

from ..models.enrollment import Enrollment
from src.app.models.course import Course
from datetime import datetime

@router.get("")
def student_course_analytics(
    course_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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
        return {"detail": "You are not enrolled in this course."}

    # --- Course info ---
    course = db.exec(select(Course).where(Course.id == course_id)).first()
    course_info = {"title": course.title, "description": course.description} if course else {}

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
    completed = 0
    total = 0
    # Videos
    total += len(total_videos)
    completed += len(videos_watched)
    # Assignments
    total += len(total_assignments)
    completed += len(assignments_submitted)
    # Quizzes
    total += len(total_quizzes)
    completed += len(quizzes_attempted)
    # Progress percentage (avoid division by zero)
    progress = int((completed / total) * 100) if total > 0 else 0

    # --- Update CourseProgress if 100% ---
    course_progress = db.exec(
        select(CourseProgress).where(
            CourseProgress.user_id == user.id,
            CourseProgress.course_id == course_id
        )
    ).first()
    now = datetime.utcnow().isoformat()
    if progress == 100:
        if course_progress:
            if not course_progress.completed:
                course_progress.completed = True
                course_progress.completed_at = now
                course_progress.progress_percentage = 100.0
                db.add(course_progress)
                db.commit()
        else:
            # Create new CourseProgress if not exists
            course_progress = CourseProgress(
                user_id=user.id,
                course_id=course_id,
                completed=True,
                completed_at=now,
                progress_percentage=100.0
            )
            db.add(course_progress)
            db.commit()
    elif course_progress:
        # Optionally update progress_percentage if not complete
        if course_progress.progress_percentage != progress:
            course_progress.progress_percentage = float(progress)
            db.add(course_progress)
            db.commit()

    return {
        "course": course_info,
        "videos": {"total": len(total_videos), "watched": len(videos_watched)},
        "assignments": {"total": len(total_assignments), "submitted": len(assignments_submitted)},
        "quizzes": {"total": len(total_quizzes), "attempted": len(quizzes_attempted)},
        "progress": progress
    }


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def submit_course_feedback(
    course_id: UUID,
    payload: CourseFeedbackCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Ensure user is enrolled and access is valid
    from ..models.enrollment import Enrollment
    from datetime import datetime
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
        raise HTTPException(status_code=403, detail="You must be enrolled in the course to submit feedback.")
    # Ensure course is completed by the user
    course_progress = db.exec(
        select(CourseProgress).where(
            CourseProgress.user_id == user.id,
            CourseProgress.course_id == course_id,
            CourseProgress.completed == True
        )
    ).first()
    if not course_progress:
        raise HTTPException(status_code=403, detail="You must complete the course before submitting feedback.")
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
