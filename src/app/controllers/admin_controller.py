from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy import func
import uuid
from typing import List
from fastapi import File, UploadFile, status
from src.app.db.session import get_db
from src.app.models.enrollment_application import EnrollmentApplication, ApplicationStatus
from src.app.models.user import User
from src.app.models.course import Course
from src.app.schemas.enrollment_application_schema import EnrollmentApplicationAdminRead, ApplicationStatusUpdate, EnrollmentApplicationRead
from src.app.utils.dependencies import get_current_admin_user
from typing import List, Optional
from src.app.models.video import Video
from src.app.models.enrollment import Enrollment
from src.app.models.notification import Notification
from src.app.models.video_progress import VideoProgress
from src.app.models.course_progress import CourseProgress
from src.app.db.session import get_db 
from uuid import UUID
from sqlalchemy.orm import selectinload 
from src.app.schemas.user import UserRead
from src.app.schemas.course import (
    AdminCourseList, AdminCourseDetail, AdminCourseStats,
    CourseCreate, CourseUpdate, CourseRead, CourseCreateAdmin
)
from src.app.schemas.video import VideoUpdate, VideoRead
from src.app.schemas.quiz import QuizCreate, QuizReadWithDetails, QuizRead
from src.app.models.quiz import Quiz, Question, Option
from src.app.schemas.notification import NotificationRead, AdminNotificationRead
import uuid
import re
from datetime import datetime, timedelta
from src.app.utils.time import get_pakistan_time
from src.app.models.assignment import Assignment, AssignmentSubmission

from typing import List
from fastapi import Form
from src.app.utils.file import save_upload_and_get_url
from src.app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentRead, AssignmentList, SubmissionRead, SubmissionGrade, SubmissionStudent, SubmissionStudentsResponse

import logging

router = APIRouter(
    tags=["Admin"]
)

@router.post("/upload/image", response_model=dict)
async def upload_image(
    file: UploadFile = File(...), 
    admin: User = Depends(get_current_admin_user)
):
    """
    Uploads an image to Cloudinary and returns the URL.
    This endpoint requires admin authentication.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only images are allowed."
        )
    
    try:
        # This utility function handles the upload and returns a public URL.
        image_url = await save_upload_and_get_url(file=file)
        return {"url": image_url}
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading the image: {str(e)}"
        )

# 1. Enrollment Management
@router.get("/users", response_model=List[UserRead])
def list_students(session: Session = Depends(get_db), admin=Depends(get_current_admin_user)):
    query = select(User).where(User.role == "student")
    return session.exec(query).all()



@router.get("/courses", response_model=list[AdminCourseList])
def admin_list_courses(db: Session = Depends(get_db), admin=Depends(get_current_admin_user)):
    courses = db.exec(select(Course)).all()
    # You can add more logic to calculate enrollments, progress, etc. if needed
    return [
        AdminCourseList(
            id=c.id,
            title=c.title,
            price=c.price,
            total_enrollments=0,  # Replace with actual logic if needed
            active_enrollments=0, # Replace with actual logic if needed
            average_progress=0.0, # Replace with actual logic if needed
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at
        ) for c in courses
    ]

@router.post("/courses", status_code=status.HTTP_201_CREATED, response_model=AdminCourseDetail)
async def create_course(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    status: str = Form("active"),
    thumbnail_url: Optional[str] = Form(None),
    difficulty_level: Optional[str] = Form(None),
    outcomes: Optional[str] = Form(None),
    prerequisites: Optional[str] = Form(None),
    curriculum: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create a new course.
    
    Note: Videos should be uploaded separately using the /api/v1/courses/{course_id}/videos endpoint.
    """
    try:
        # Create the course
        course = Course(
            title=title,
            description=description,
            price=price,
            status=status,
            thumbnail_url=thumbnail_url,
            difficulty_level=difficulty_level,
            outcomes=outcomes,
            prerequisites=prerequisites,
            curriculum=curriculum,
            created_by=admin.id,
            updated_by=admin.id
        )
        
        db.add(course)
        db.commit()
        db.refresh(course)
        return course
        
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create course: {str(e)}"
        )


@router.get("/courses/{course_id}", response_model=AdminCourseDetail)
def get_course_detail(
    course_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """
    Get detailed information about a specific course.
    """
    course = db.exec(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.videos),
            selectinload(Course.preview_video)
        )
    ).first()

    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    return course 


# 2. Notifications
@router.get("/notifications", response_model=List[AdminNotificationRead])
def get_notifications(session: Session = Depends(get_db), admin=Depends(get_current_admin_user)):
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

# 3. Course Management
@router.put("/courses/{course_id}")
async def update_course(
    request: Request,
    course_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Update an existing course with comprehensive validation"""
    # ─── Logging for Vercel Debugging ────────────────────────────────────────
    logging.basicConfig(level=logging.INFO)
    logging.info(f"--- Admin Course Update Request ---")
    logging.info(f"Received request for course_id: {course_id}")
    logging.info(f"Request Headers: {request.headers}")

    try:
        body = await request.body()
        logging.info(f"Raw Request Body: {body.decode('utf-8', errors='ignore')}")
    except Exception as e:
        logging.error(f"Error reading request body: {e}")

    try:
        # Parse form data since the frontend is sending multipart/form-data
        form_data = await request.form()
        logging.info(f"Parsed Form Data: {form_data}")
        course_update = CourseUpdate.parse_obj(form_data)
    except Exception as e:
        logging.error(f"Error parsing form data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse form data: {e}"
        )
    # ────────────────────────────────────────────────────────────────────────

    try:
        # Validate course_id format
        try:
            course_uuid = uuid.UUID(course_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid course ID format"
            )

        # Get existing course
        course = db.exec(
            select(Course).where(Course.id == course_uuid)
        ).first()
        
        if not course:
            raise HTTPException(
                status_code=404,
                detail="Course not found"
            )

        # Validate update data
        update_data = course_update.dict(exclude_unset=True)
        
        if "title" in update_data:
            if not update_data["title"] or len(update_data["title"].strip()) < 3:
                raise HTTPException(
                    status_code=400,
                    detail="Course title must be at least 3 characters long"
                )
            # Check for duplicate title
            existing_course = db.exec(
                select(Course)
                .where(
                    Course.title == update_data["title"],
                    Course.id != course_uuid
                )
            ).first()
            if existing_course:
                raise HTTPException(
                    status_code=400,
                    detail="A course with this title already exists"
                )

        if "description" in update_data and len(update_data["description"].strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Course description must be at least 10 characters long"
            )

        if "price" in update_data and update_data["price"] < 0:
            raise HTTPException(
                status_code=400,
                detail="Course price cannot be negative"
            )

        # Update course fields
        for key, value in update_data.items():
            setattr(course, key, value)
            
        course.updated_by = admin.email
        course.updated_at = datetime.utcnow()
        
        try:
            db.add(course)
            db.commit()
            db.refresh(course)
            
            # Return simple success message
            return {
                "message": "Course updated successfully"
            }
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error updating course in database: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error updating course: {str(e)}"
        )

# Delete a course (hard delete)
@router.delete("/courses/{course_id}", status_code=status.HTTP_200_OK)
def delete_course(
    course_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Deletes a course and all its related data (hard delete).

    This function first finds the course by its ID. It then manually sets the
    `preview_video_id` to `None` to break a potential circular dependency
    that can prevent deletion. After committing this change, it proceeds to
    delete the course. The `cascade="all, delete-orphan"` settings in the
    SQLModel relationships will handle the deletion of all related entities
    like videos, enrollments, quizzes, etc.
    """
    # Find the course using a direct lookup by primary key
    course = db.get(Course, course_id)
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    try:
        # Manually break the circular dependency with the preview video.
        # This is necessary because the foreign key in the database might not
        # have ON DELETE SET NULL. Setting it to None here resolves the conflict
        # before the deletion is attempted.
        if course.preview_video_id is not None:
            course.preview_video_id = None
            db.add(course)
            db.commit()

        # Now, delete the course. The cascade rules in the models
        # will handle the deletion of related entities.
        db.delete(course)
        db.commit()
        
        return {"message": "Course deleted successfully"}

    except Exception as e:
        # If any error occurs during the process, rollback the transaction
        # to leave the database in a consistent state.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the course: {str(e)}"
        )
@router.get("/dashboard/stats", response_model=dict)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get overall platform statistics for admin dashboard"""
    try:
        # Get total courses
        total_courses = db.exec(select(func.count(Course.id))).first()
        
        # Get total enrollments
        total_enrollments = db.exec(select(func.count(Enrollment.id))).first()
        
        # Get active enrollments (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(
                Enrollment.status == "approved",
                Enrollment.is_accessible == True
            )
        ).first()
        
        # Get total revenue
        total_revenue = db.exec(
            select(func.sum(Course.price))
            .join(Enrollment)
            .where(Enrollment.status == "approved")
        ).first() or 0
        
        # Get completion rate
        completed_courses = db.exec(
            select(func.count(CourseProgress.id))
            .where(CourseProgress.completed == True)
        ).first()
        
        completion_rate = (completed_courses / total_enrollments * 100) if total_enrollments > 0 else 0
        
        # Get recent enrollments (last 30 days)
        recent_enrollments = db.exec(
            select(func.count(Enrollment.id))
            .where(
                Enrollment.status == "approved",
                Enrollment.is_accessible == True
            )
        ).first()
        
        return {
            "total_courses": total_courses,
            "total_enrollments": total_enrollments,
            "active_enrollments": active_enrollments,
            "recent_enrollments": recent_enrollments,
            "total_revenue": round(total_revenue, 2),
            "completion_rate": round(completion_rate, 2),
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching dashboard stats: {str(e)}"
        )

@router.get("/courses", response_model=List[AdminCourseList])
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
    course_id: str,
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
        
        # Import VideoRead from course schema which matches our needs
        from app.schemas.course import VideoRead
        
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

from src.app.utils.email import send_application_approved_email, send_enrollment_rejected_email

@router.put("/enrollments/approve")
def approve_enrollment_by_user(
    user_id: str,
    course_id: str,
    duration_months: int = Query(..., description="Duration of access in months"),
    session: Session = Depends(get_db),
    admin=Depends(get_current_admin_user)
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
    user_id: str,
    course_id: str,
    session: Session = Depends(get_db),
    admin=Depends(get_current_admin_user)
):
    """Test endpoint to set an enrollments expiration date to today.

    Args:
        user_id (str): ID of the user whose enrollment will be updated
        course_id (str): ID of the course for the enrollment
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
    course_id: UUID,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
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
    course_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
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
    course_id: str,
    assignment_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Remove an assignment."""
    assign = db.get(Assignment, uuid.UUID(assignment_id))
    if not assign or str(assign.course_id) != course_id:
        raise HTTPException(404, "Assignment not found")
    db.delete(assign)
    db.commit()
    return
@router.get(
    "/courses/{course_id}/assignments/{assignment_id}/submissions/students",
    response_model=SubmissionStudentsResponse,
)
def admin_list_on_time_submissions(
    course_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user),
):
    # 1) load assignment and its course
    stmt = select(Assignment).where(Assignment.id == assignment_id).options(selectinload(Assignment.course))
    assignment = db.exec(stmt).first()
    if not assignment or str(assignment.course_id) != str(course_id):
        raise HTTPException(status_code=404, detail="Assignment not found in this course")

    # 2) load submissions + students
    stmt = (
        select(AssignmentSubmission)
        .where(AssignmentSubmission.assignment_id == assignment_id)
        .options(selectinload(AssignmentSubmission.student))
    )
    submissions_from_db = db.exec(stmt).all()

    students = []
    for sub in submissions_from_db:
        if sub.student:
            students.append(
                SubmissionStudent(
                    id=sub.id,
                    student_id=sub.student.id,
                    email=sub.student.email,
                    full_name=sub.student.full_name,
                    submitted_at=sub.submitted_at,
                    content_url=sub.content_url,
                    grade=sub.grade,
                    feedback=sub.feedback
                )
            )

    # 3) return with the correct schema
    assignment_details = AssignmentRead(
        id=assignment.id,
        course_id=assignment.course_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        status='n/a',  # Status is student-specific, not applicable here
        course_title=assignment.course.title,
        submission=None
    )

    return SubmissionStudentsResponse(
        assignment=assignment_details,
        submissions=students,
    )

@router.put(
    "/courses/{course_id}/assignments/{assignment_id}/submissions/{submission_id}/grade",
    response_model=SubmissionRead,
    summary="Grade a student's assignment submission",
)
def admin_grade_submission(
    course_id: UUID,
    assignment_id: UUID,
    submission_id: UUID,
    payload: SubmissionGrade,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user),
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
    course_id: str,
    assignment_id: str,
    payload: AssignmentUpdate,  # Changed from AssignmentCreate
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Update an assignment's title, description, and due date."""
    assignment = db.get(Assignment, assignment_id)
    if not assignment or str(assignment.course_id) != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Get the update data, excluding unset fields
    update_data = payload.dict(exclude_unset=True)

    # Update the assignment object with the new data
    for key, value in update_data.items():
        setattr(assignment, key, value)

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # Manually construct the response to include the course_title
    return AssignmentRead(
        id=assignment.id,
        course_id=assignment.course_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        status='n/a',  # Status is not relevant in this context
        course_title=assignment.course.title,
        submission=None
    )

@router.post("/admin/quizzes", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    # Check if course exists
    course = db.get(Course, quiz_data.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Create Quiz instance
    new_quiz = Quiz(
        course_id=quiz_data.course_id,
        title=quiz_data.title,
        description=quiz_data.description,
        due_date=quiz_data.due_date
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    # Create Questions and Options
    for q_data in quiz_data.questions:
        new_question = Question(
            quiz_id=new_quiz.id,
            text=q_data.text,
            is_multiple_choice=True # You can adjust this based on your needs
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)

        for o_data in q_data.options:
            new_option = Option(
                question_id=new_question.id,
                text=o_data.text,
                is_correct=o_data.is_correct
            )
            db.add(new_option)
    
    db.commit()
    db.refresh(new_quiz) # Refresh to get all nested objects

    return new_quiz
def get_admin_user(current_user: User = Depends(get_current_admin_user)) -> User:
    """Dependency to ensure the user is an admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    return current_user

@router.get("/applications", response_model=List[EnrollmentApplicationAdminRead], dependencies=[Depends(get_admin_user)])
def get_all_applications(
    session: Session = Depends(get_db)
) -> List[EnrollmentApplicationAdminRead]:
    # This query joins the application with the user and course to get their details
    statement = select(EnrollmentApplication, User.email, Course.title).join(User).join(Course)
    results = session.exec(statement).all()
    
    # Format the results into the Pydantic schema
    applications = [
        EnrollmentApplicationAdminRead(
            id=app.id,
            student_email=email,
            course_title=title,
            status=app.status
        )
        for app, email, title in results
    ]
    return applications

@router.patch("/applications/{application_id}/status", response_model=EnrollmentApplicationRead, dependencies=[Depends(get_admin_user)])
def update_application_status(
    application_id: uuid.UUID,
    status_update: ApplicationStatusUpdate,
    session: Session = Depends(get_db)
) -> EnrollmentApplication:
    application = session.get(EnrollmentApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = status_update.status
    session.add(application)
    session.commit()
    session.refresh(application)

    if status_update.status == ApplicationStatus.APPROVED:
        user = session.get(User, application.user_id)
        course = session.get(Course, application.course_id)
        if user and course:
            send_application_approved_email(
                to_email=user.email, 
                course_title=course.title
            )

    elif status_update.status == ApplicationStatus.REJECTED:
        user = session.get(User, application.user_id)
        course = session.get(Course, application.course_id)
        if user and course:
            rejection_reason = status_update.message or "No reason provided."
            send_enrollment_rejected_email(
                to_email=user.email, 
                course_title=course.title, 
                rejection_reason=rejection_reason
            )

    return application    
