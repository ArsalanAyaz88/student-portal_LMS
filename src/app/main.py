# ───────────────────────────────────────────────────────────────
import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel, create_engine, select
from datetime import datetime
from sqlalchemy import inspect
from dotenv import load_dotenv
import logging

# ─── Local imports ─────────────────────────────────────────────
from src.app.db.session import create_db_and_tables
from src.app.models.course import Course
from src.app.models.video import Video

# Import all necessary schemas for model_rebuild
from src.app.schemas.user import UserRead
from src.app.schemas.course import CourseRead, CourseExploreDetail, CourseDetail
from src.app.schemas.enrollment import EnrollmentApplicationRead
from src.app.schemas.video import VideoRead, VideoWithProgress, VideoPreview

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
    # Step 1: Create database tables
    create_db_and_tables()

    # Step 2: Rebuild all Pydantic models in correct order
    logging.basicConfig(level=logging.INFO) # Basic config for logging
    try:
        # --- Tier 1: Base models with no or minimal dependencies ---
        logging.info("Rebuilding UserRead...")
        UserRead.model_rebuild()
        logging.info("Rebuilding CourseRead...")
        CourseRead.model_rebuild()
        logging.info("Rebuilding VideoRead...")
        VideoRead.model_rebuild()
        logging.info("Rebuilding VideoPreview...")
        VideoPreview.model_rebuild()

        # --- Tier 2: Models that depend on Tier 1 ---
        logging.info("Rebuilding CourseExploreDetail...")
        CourseExploreDetail.model_rebuild()
        logging.info("Rebuilding CourseDetail...")
        CourseDetail.model_rebuild()
        logging.info("Rebuilding VideoWithProgress...")
        VideoWithProgress.model_rebuild()

        # --- Tier 3: Models that depend on Tier 1 and/or Tier 2 ---
        logging.info("Rebuilding EnrollmentApplicationRead...")
        EnrollmentApplicationRead.model_rebuild()

        logging.info("All Pydantic models rebuilt successfully")
    except Exception as e:
        logging.error(f"Failed to rebuild Pydantic models: {e}", exc_info=True)
        raise

    # Step 3: Log relationships (optional)
    logging.info("Course relationships: %s", inspect(Course).relationships)
    logging.info("Video relationships: %s", inspect(Video).relationships)

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