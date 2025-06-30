# File: app/controllers/admin_controller.py

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, File, UploadFile
from sqlmodel import Session, select, func
from typing import List, Optional
from src.app.models.user import User
from src.app.models.course import Course
from src.app.models.video import Video
from src.app.models.enrollment import Enrollment
from src.app.models.notification import Notification
from src.app.models.video_progress import VideoProgress
from src.app.models.course_progress import CourseProgress
from src.app.db.session import get_db
from src.app.utils.dependencies import get_current_admin_user
from uuid import UUID
from sqlalchemy.orm import selectinload 
from src.app.schemas.user import UserRead
from src.app.schemas.course import (
    AdminCourseList, AdminCourseDetail, AdminCourseStats,
    CourseCreate, CourseUpdate, CourseRead, CourseCreateAdmin
)
from src.app.schemas.video import VideoUpdate, VideoRead
from src.app.schemas.notification import NotificationRead, AdminNotificationRead
import uuid
import re
from datetime import datetime, timedelta
from src.app.utils.time import get_pakistan_time
from src.app.models.assignment import Assignment, AssignmentSubmission
from src.app.models.quiz import Quiz, Question, Option
from typing import List
from fastapi import Form
from src.app.utils.file import save_upload_and_get_url
from src.app.schemas.assignment import AssignmentCreate, AssignmentRead, AssignmentList, SubmissionRead, SubmissionGrade, SubmissionStudent, SubmissionStudentsResponse
from src.app.schemas.quiz import QuizCreate, QuizRead, QuizUpdate, QuizResult, QuizSubmissionStatus
import logging

router = APIRouter(
    tags=["Admin"]
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

# 1b. Create a new course with preview video and videos
@router.post("/courses", status_code=status.HTTP_201_CREATED, response_model=AdminCourseDetail)
async def create_course(
    course_data: CourseCreateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Create a new course.

    This endpoint is used by an Admin to create a new course.
    The request should be standard JSON.

    **Example Request Body:**
    ```json
    {
      "title": "The Ultimate Python Course",
      "description": "A comprehensive course covering all aspects of Python programming.",
      "price": 99.99,
      "difficulty_level": "Intermediate",
      "outcomes": "By the end of this course, you will be able to:\\n- Write clean and efficient Python code.\\n- Build complex applications.\\n- Understand advanced Python concepts.",
      "prerequisites": "Basic understanding of programming concepts.",
      "curriculum": "1. Python Basics\\n2. Data Structures\\n3. Object-Oriented Programming\\n4. Web Development with Flask\\n5. Data Science with Pandas and NumPy",
      "status": "active",
      "preview_video": {
        "youtube_url": "https://www.youtube.com/watch?v=preview_video_id",
        "title": "Course Preview",
        "description": "A quick look at what this course offers."
      },
      "videos": [
        {
          "youtube_url": "https://www.youtube.com/watch?v=video_one_id",
          "title": "Chapter 1: Introduction",
          "description": "Setting up your Python environment."
        },
        {
          "youtube_url": "https://www.youtube.com/watch?v=video_two_id",
          "title": "Chapter 2: Data Types",
          "description": "An in-depth look at Python's data types."
        }
      ]
    }
    ```

    **Returns:**
    The newly created course object if successful.

    **Raises:**
    - `HTTPException(400)`: If a course with the same title already exists.
    - `HTTPException(500)`: For any other server-side errors.
    """
    # Check for existing course
    if db.exec(select(Course).where(Course.title == course_data.title)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course with this title already exists")

    # 1. Create all objects in memory first
    new_course = Course(
        title=course_data.title,
        description=course_data.description,
        price=course_data.price,
        difficulty_level=course_data.difficulty_level,
        outcomes=course_data.outcomes,
        prerequisites=course_data.prerequisites,
        curriculum=course_data.curriculum,
        status=course_data.status,
        created_by=str(admin.id),
        updated_by=str(admin.id),
        created_at=get_pakistan_time(),
        updated_at=get_pakistan_time()
    )

    # 2. Create all video objects first
    all_video_objects = []
    preview_video_obj = None
    if course_data.preview_video:
        preview_video_obj = Video(**course_data.preview_video.dict())
        all_video_objects.append(preview_video_obj)

    if course_data.videos:
        for video_data in course_data.videos:
            all_video_objects.append(Video(**video_data.dict()))

    # 3. Establish relationships in the correct order
    # This populates video.course_id via back_populates
    new_course.videos = all_video_objects

    # This uses the 'post_update' strategy to break the circular dependency
    if preview_video_obj:
        new_course.preview_video = preview_video_obj

    # 3. Add only the parent object to the session. Cascade will handle the rest.
    db.add(new_course)

    # 4. Commit the entire transaction. SQLAlchemy will resolve the insert order.
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database commit failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while creating the course.")

    # 5. Refresh the objects to get DB-generated values
    db.refresh(new_course)
    if new_course.preview_video:
        db.refresh(new_course.preview_video)
    for video in new_course.videos:
        db.refresh(video)

    return new_course


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
    course_id: str,
    course_update: CourseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Update an existing course with comprehensive validation"""
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

from src.app.utils.email import send_enrollment_approved_email

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
    "/admin/courses/{course_id}/assignments",
    response_model=AssignmentRead,
    status_code=201
)
def admin_create_assignment(
    course_id: str,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Create a new assignment for a course."""
    try:
        assign = Assignment(
            id=uuid.uuid4(),
            course_id=uuid.UUID(course_id),
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date
        )
        db.add(assign)
        db.commit()
        db.refresh(assign)
        return assign
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error creating assignment: {e}")

@router.get(
    "/admin/courses/{course_id}/assignments",
    response_model=List[AssignmentRead]
)
def admin_list_assignments(
    course_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """List all assignments under a given course."""
    stmt = select(Assignment).where(Assignment.course_id == uuid.UUID(course_id))
    return db.exec(stmt).all()

@router.delete(
    "/admin/courses/{course_id}/assignments/{assignment_id}",
    status_code=204
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
    # 1) load assignment
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise HTTPException(404, "Assignment not found")

    # 2) load submissions + students
    stmt = (
        select(AssignmentSubmission)
        .where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.submitted_at <= assignment.due_date
        )
        .options(selectinload(AssignmentSubmission.student))
    )
    subs = db.exec(stmt).all()

    students = [
        SubmissionStudent(
            id           = sub.id,
            student_id   = sub.student.id,
            email        = sub.student.email,
            full_name    = sub.student.full_name,
            submitted_at = sub.submitted_at,
            content_url  = sub.content_url,
            grade        = sub.grade,
            feedback     = sub.feedback,
        )
        for sub in subs
    ]

    # 3) return with the correct schema
    return SubmissionStudentsResponse(
        assignment  = AssignmentRead.from_orm(assignment),
        submissions = students,
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
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user),
):
    """Update an assignment's title, description, and due date."""
    assignment = db.get(Assignment, assignment_id)
    if not assignment or str(assignment.course_id) != course_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assignment.title = payload.title
    assignment.description = payload.description
    assignment.due_date = payload.due_date
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment

# ──────────────────────────────────────────────────────────────────────────────
# 2. Quiz endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/courses/{course_id}/quizzes", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def admin_create_quiz(
    course_id: str,
    payload: QuizCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """
    Create a new quiz with its questions and options in a single transaction.
    """
    # Validate course_id format
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course ID format. Please provide a valid UUID."
        )
    
    # Check if course exists
    course = db.get(Course, course_uuid)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Course not found"
        )

    # Create the quiz object directly from the payload
    new_quiz = Quiz(
        course_id=course.id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date
    )

    questions_to_create = []
    for q_data in payload.questions:
        new_question = Question(
            text=q_data.text,
            is_multiple_choice=q_data.is_multiple_choice
        )
        
        options_to_create = []
        for o_data in q_data.options:
            new_option = Option(text=o_data.text, is_correct=o_data.is_correct)
            options_to_create.append(new_option)
        
        new_question.options = options_to_create
        questions_to_create.append(new_question)
    
    new_quiz.questions = questions_to_create

    try:
        # Add only the parent object to the session.
        # The relationships with cascade will handle the rest.
        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)
        return new_quiz
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )


@router.get("/courses/{course_id}/quizzes", response_model=List[QuizRead])
def admin_list_quizzes(
    course_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """List all quizzes for a course."""
    # Validate course_id format
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course ID format. Please provide a valid UUID."
        )
    
    # Check if course exists
    course = db.get(Course, course_uuid)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Course not found"
        )
        
    stmt = select(Quiz).where(Quiz.course_id == course_uuid)
    return db.exec(stmt).all()


@router.put("/courses/{course_id}/quizzes/{quiz_id}")
def admin_update_quiz(
    course_id: str,
    quiz_id: str,
    payload: QuizUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """
    Update a quiz's details, questions, and options.
    This performs a partial update - only the provided fields will be updated.
    """
    # Validate UUID formats
    try:
        quiz_uuid = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid quiz ID format: {quiz_id}. Please provide a valid UUID."
        )
    
    try:
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid course ID format: {course_id}. Please provide a valid UUID."
        )

    # Get the quiz with relationships loaded
    quiz = db.exec(
        select(Quiz)
        .where(Quiz.id == quiz_uuid, Quiz.course_id == course_uuid)
        .options(selectinload(Quiz.questions).selectinload(Question.options))
    ).first()
    
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found in this course"
        )

    # Update basic fields if provided
    update_data = payload.dict(exclude_unset=True)
    
    # Handle basic fields (title, description, due_date)
    basic_fields = ['title', 'description', 'due_date']
    for field in basic_fields:
        if field in update_data:
            setattr(quiz, field, update_data[field])
    
    # Handle questions if provided
    if 'questions' in update_data and update_data['questions'] is not None:
        # Clear existing questions (this will cascade to options)
        for question in quiz.questions:
            db.delete(question)
        
        # Add new questions and options
        for q_data in payload.questions:
            new_question = Question(
                quiz_id=quiz.id,
                text=q_data.text,
                is_multiple_choice=q_data.is_multiple_choice
            )
            
            options_to_create = []
            for o_data in q_data.options:
                new_option = Option(
                    text=o_data.text, 
                    is_correct=o_data.is_correct
                )
                options_to_create.append(new_option)
            
            new_question.options = options_to_create
            quiz.questions.append(new_question)
    
    try:
        db.add(quiz)
        db.commit()
        return {"message": "Quiz updated successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Error updating quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during update: {e}"
        )


@router.get("/courses/{course_id}/quizzes/{quiz_id}/submission_status", response_model=List[QuizSubmissionStatus])
def admin_get_quiz_submission_status(
    course_id: str,
    quiz_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Get the submission status for a quiz."""
    quiz = db.get(Quiz, uuid.UUID(quiz_id))
    if not quiz or str(quiz.course_id) != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")

    statuses = []
    for sub in quiz.submissions:
        is_on_time = True
        if quiz.due_date and sub.submitted_at > quiz.due_date:
            is_on_time = False
        
        statuses.append(
            QuizSubmissionStatus(
                submission_id=sub.id,
                student_id=sub.student_id,
                submitted_at=sub.submitted_at,
                is_on_time=is_on_time
            )
        )
    return statuses


@router.get("/courses/{course_id}/quizzes/{quiz_id}/submissions", response_model=List[QuizResult])
def admin_get_quiz_submissions(
    course_id: str,
    quiz_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Get all submissions for a quiz."""
    quiz = db.get(Quiz, uuid.UUID(quiz_id))
    if not quiz or str(quiz.course_id) != course_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz.submissions


@router.delete("/courses/{course_id}/quizzes/{quiz_id}", status_code=status.HTTP_200_OK)
def admin_delete_quiz(
    course_id: str,
    quiz_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """
    Remove a quiz and its related questions and options.
    """
    # Validate UUID formats
    try:
        quiz_uuid = uuid.UUID(quiz_id)
        course_uuid = uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format for course or quiz ID. Please provide valid UUIDs."
        )

    # Check if course exists
    course = db.get(Course, course_uuid)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Get the quiz with relationships loaded
    quiz = db.exec(
        select(Quiz)
        .where(Quiz.id == quiz_uuid, Quiz.course_id == course_uuid)
        .options(selectinload(Quiz.questions).selectinload(Question.options))
    ).first()
    
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found in this course"
        )

    try:
        db.delete(quiz)
        db.commit()
        return {"message": "Quiz deleted successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the quiz: {str(e)}"
        )
