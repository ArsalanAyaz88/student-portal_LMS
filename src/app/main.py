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
from src.app.routers import (
    auth_router,
    profile_router,
    course_router,
    admin_router,
    student_assignment_router as sa_router,
    student_quiz_router as sq_router,
    student_dashboard_router,
    admin_quiz_router,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=False, # Allows credentials (e.g., Authorization headers)
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ─── DB tables on startup ──────────────────────────────────────
@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()

# Log model relationships (optional)
@app.on_event("startup")
async def startup_event() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("Course relationships: %s", inspect(Course).relationships)
    logging.info("Video relationships: %s", inspect(Video).relationships)

# ─── Routers ───────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile_router.router, prefix="/api/profile", tags=["Profile"])

app.include_router(course_router.router, prefix="/api/courses", tags=["Courses"])
app.include_router(enrollment_controller.router, prefix="/api/enrollments", tags=["Enrollments"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])
app.include_router(sa_router.router, prefix="/api/student/assignments")
app.include_router(sq_router.router, prefix="/api")
app.include_router(
    student_dashboard_router.router,
    prefix="/api/student/dashboard",
    tags=["Student Dashboard"],
)

# Include the refactored admin quiz routers
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