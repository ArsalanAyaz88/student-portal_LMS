# ───────────────────────────────────────────────────────────────
import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers
from dotenv import load_dotenv
import logging 

# ─── Local imports ─────────────────────────────────────────────
from src.app.db.session import create_db_and_tables

# --- Explicitly Import All Models ---
# This is the definitive fix to ensure all models are loaded into SQLAlchemy's
# metadata before any mapper configuration or table creation is attempted.
# It resolves circular dependency issues that can occur during startup.
from src.app.models import (
    User, Profile, OAuthAccount, PasswordReset, BankAccount,
    Course, Video, Assignment, Quiz, Question, Option,
    Enrollment, EnrollmentApplication, CourseProgress, VideoProgress,
    QuizAuditLog, CourseFeedback, PaymentProof, Notification, Certificate
)
# --- End of Explicit Imports ---

# Import routers
from src.app.routers import (
    auth_router, profile_router, course_router, sa_router, sq_router, 
    student_dashboard_router, admin_quiz_router, admin_router
)
from src.app.controllers import enrollment_controller

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
    allow_origins=["https://lmsfrontend-neon.vercel.app", "https://lmsfrontend2.vercel.app", "http://localhost:3000", "https://frontend-rho-nine-62.vercel.app", "http://192.168.100.132:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Consolidated Startup Events ────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logging.info("Configuring SQLAlchemy mappers...")
    try:
        # This resolves all relationships between models before any other action.
        configure_mappers()
        logging.info("Mappers configured successfully.")
    except Exception as e:
        logging.error(f"Mapper configuration failed: {e}", exc_info=True)
        raise

    # Step 2: Create database and tables
    logging.info("Creating database and tables...")
    try:
        create_db_and_tables()
    except Exception as e:
        logging.error(f"Failed to create database and tables: {e}", exc_info=True)
        raise

# ─── Routers ───────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile_router.router, prefix="/api/profile", tags=["Profile"])
app.include_router(course_router.router, prefix="/api/courses", tags=["Courses"])
app.include_router(enrollment_controller.router, prefix="/api", tags=["Enrollments"])
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
