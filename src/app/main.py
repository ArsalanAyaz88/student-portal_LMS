# ───────────────────────────────────────────────────────────────
import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel, create_engine, select
import logging
from sqlalchemy import inspect
from dotenv import load_dotenv
import cloudinary
from datetime import datetime

# ─── Local imports ─────────────────────────────────────────────
from src.app.db.session import create_db_and_tables
from src.app.models.course import Course
from src.app.models.video import Video

# Import all necessary schemas for model_rebuild
from src.app.schemas.user import UserRead
from src.app.schemas.course import CourseRead, CourseExploreDetail, CourseDetail
from src.app.schemas.enrollment import EnrollmentApplicationRead
from src.app.schemas.video import VideoRead, VideoWithProgress

# Import routers
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

# ─── Middlewares ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lmsfrontend-neon.vercel.app", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Consolidated Startup Events ────────────────────────────────
@app.on_event("startup")
async def startup_tasks():
    """
    Run all startup tasks in the correct order to prevent errors.
    """
    print("INFO:     Running startup tasks...")

    # Step 1: Create database and tables
    print("INFO:     Creating database and tables...")
    create_db_and_tables()

    # Step 2: Rebuild all Pydantic models in the correct dependency order
    print("INFO:     Rebuilding Pydantic models...")
    try:
        # Base models first
        UserRead.model_rebuild()
        CourseRead.model_rebuild()
        VideoRead.model_rebuild()

        # Dependent models next
        CourseExploreDetail.model_rebuild()
        CourseDetail.model_rebuild()
        VideoWithProgress.model_rebuild()
        EnrollmentApplicationRead.model_rebuild()
        print("INFO:     Pydantic models rebuilt successfully.")
    except Exception as e:
        logging.error(f"Failed to rebuild Pydantic models: {e}", exc_info=True)
        # Depending on the desired behavior, you might want to raise the exception
        # to prevent the app from starting in a broken state.
        raise

    # Step 3: Log relationships (optional for debugging)
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
app.include_router(student_dashboard_router.router, prefix="/api/student/dashboard", tags=["Student Dashboard"])
app.include_router(admin_quiz_router.quiz_router, prefix="/api/admin/quizzes")
app.include_router(admin_quiz_router.question_router, prefix="/api/admin/questions")
app.include_router(admin_quiz_router.submission_router, prefix="/api/admin/submissions")

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