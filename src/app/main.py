# ───────────────────────────────────────────────────────────────
# File:  src/app/main.py
# ───────────────────────────────────────────────────────────────
import os
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from dotenv import load_dotenv
import cloudinary

# ─── Local imports ─────────────────────────────────────────────
from src.app.db.session import create_db_and_tables
from src.app.models.course import Course
from src.app.models.video import Video
from src.app.controllers import (
    auth_controller,
    admin_controller,
    enrollment_controller
)
from src.app.schemas import video, course, user
from src.app.schemas.enrollment import EnrollmentApplicationRead
from src.app.schemas.user import UserRead
from src.app.schemas.course import CourseRead



from src.app.routers import (
    auth_router,
    profile_router,
    course_router,
    student_assignment_router as sa_router,
    student_quiz_router as sq_router,
    student_dashboard_router,
    admin_quiz_router,

    enrollment_router,
    admin_router
)


# ─── Env setup ─────────────────────────────────────────────
load_dotenv()

# ─── FastAPI app ───────────────────────────────────────────────
app = FastAPI(  
    title="Student Portal LMS",
    description="API for EduTech platform",
    version="1.0.0",
)

# Harmless print statement to trigger a new deployment
print("FastAPI application starting up...")

# Harmless print statement to trigger a new deployment
print("FastAPI application starting up...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lmsfrontend-neon.vercel.app", "http://localhost:5173", "http://localhost:3000"],  # Allows specific origins
    allow_credentials=True, # Allows credentials (e.g., Authorization headers)
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ─── Consolidated Startup Events ────────────────────────────────
@app.on_event("startup")
async def startup_tasks():
    """
    Run all startup tasks in the correct order.
    """
    print("INFO:     Running startup tasks...")
    
    # 1. Create database and tables
    print("INFO:     Creating database and tables...")
    create_db_and_tables()
    
    # 2. Rebuild Pydantic models to resolve forward references
    print("INFO:     Rebuilding Pydantic models in correct order...")
    
    # --- Stage 1: Base models with no dependencies ---
    UserRead.model_rebuild()
    CourseRead.model_rebuild()
    video.VideoRead.model_rebuild()

    # --- Stage 2: Dependent models ---
    # These models depend on the base models rebuilt above.
    EnrollmentApplicationRead.model_rebuild()
    video.VideoWithProgress.model_rebuild()
    course.CourseExploreDetail.model_rebuild()
    course.CourseDetail.model_rebuild()

    # 3. Log model relationships (optional, for debugging)
    logging.basicConfig(level=logging.INFO)
    logging.info("Course relationships: %s", inspect(Course).relationships)
    logging.info("Video relationships: %s", inspect(Video).relationships)
    print("INFO:     Startup tasks completed.")

# ─── Routers ───────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile_router.router, prefix="/api/profile", tags=["Profile"])
app.include_router(course_router.router, prefix="/api/courses", tags=["Courses"])

app.include_router(enrollment_router.router, prefix="/api/enrollments", tags=["Enrollments"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])
app.include_router(sa_router.router, prefix="/api/student/assignments")
app.include_router(sq_router.router, prefix="/api/student")
app.include_router(
    student_dashboard_router.router,
    prefix="/api/student/dashboard",
    tags=["Student Dashboard"],
)

# Include the refactored admin quiz routers
app.include_router(admin_quiz_router.quiz_router, prefix="/api/admin/quizzes")
app.include_router(admin_quiz_router.question_router, prefix="/api/admin/questions")
app.include_router(admin_quiz_router.submission_router, prefix="/api/admin/submissions")

# Include video router


# ─── Simple endpoints ──────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "Welcome to EduTech API",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}