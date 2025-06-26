# File: app/main.py
# File location: src/app/main.py
import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from src.app.models.course import Course
from src.app.models.video import Video

# Import routers
from src.app.routers import (
    auth_router,
    profile_router,
    course_router,
    admin_router,
    student_assignment_router as sa_router,
    student_quiz_router as sq_router,
    student_dashboard_router
)
from src.app.controllers import enrollment_controller
from src.app.utils.dependencies import get_current_admin_user

# Import database setup
from src.app.db.session import create_db_and_tables

# Import Cloudinary configuration
import cloudinary
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

app = FastAPI(
    title="EduTech API",
    description="API for EduTech platform",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080"
]

# Add CORSMiddleware to the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specific origins
    allow_credentials=False,  # Allow credentials such as cookies
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


# Create database tables on startup
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Log SQLAlchemy mapper relationships for Course and Video on startup
@app.on_event("startup")
async def startup_event():
    logging.basicConfig(level=logging.INFO)
    insp_course = inspect(Course)
    insp_video = inspect(Video)
    logging.info("Course relationships: %s", insp_course.relationships)
    logging.info("Video relationships: %s", insp_video.relationships)

# Include routers
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile_router.router, prefix="/api/profile", tags=["Profile"])
app.include_router(course_router.router, prefix="/api/courses", tags=["Courses"])
app.include_router(enrollment_controller.router, prefix="/api/enrollments", tags=["Enrollments"])

app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])
app.include_router(sa_router.router, prefix="/api/student/assignments")
app.include_router(sq_router.router, prefix="/api/student/quizzes")
app.include_router(student_dashboard_router.router, prefix="/api/student/dashboard", tags=["Student Dashboard"])



@app.get("/")
async def root():
    return {
        "message": "Welcome to EduTech API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

# Test endpoint for CORS debugging

# Simple health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()} 