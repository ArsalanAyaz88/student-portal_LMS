# File: app/main.py
# File location: src/app/main.py
import os
import logging
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

# Define allowed CORS origins based on environment
is_production = os.getenv('ENVIRONMENT') == 'production'

# In production, only allow specific origins
if is_production:
    cors_origins = [
        "https://lmsfrontend-neon.vercel.app",  # Replace with your production frontend URL
    ]
else:
    # Explicitly list allowed origins for development
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ]

app = FastAPI(
    title="EduTech API",
    description="API for EduTech platform",
    version="1.0.0"
)

# Add CORS middleware with more detailed configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "*",
        "Content-Type",
        "Authorization",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials"
    ],
    expose_headers=[
        "Content-Range",
        "X-Total-Count",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials"
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add middleware to log CORS headers for debugging
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get('origin')
    
    # Log CORS-related headers for debugging
    if origin and origin in cors_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        
    # Log request details for debugging
    print(f"\n--- Request ---")
    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Origin: {origin}")
    print(f"Headers: {dict(request.headers)}")
    print(f"CORS Allowed Origins: {cors_origins}")
    print(f"Environment: {'production' if is_production else 'development'}")
    print(f"Response Headers: {dict(response.headers)}")
    
    return response

# Log CORS settings on startup
print(f"\n--- CORS Configuration ---")
print(f"Allowed Origins: {cors_origins}")
print(f"Environment: {'production' if is_production else 'development'}")
print(f"Allow Credentials: True")
print("---\n")

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
@app.get("/test-cors")
async def test_cors(request: Request):
    return {
        "message": "CORS test successful",
        "origin": request.headers.get("origin"),
        "cors_allowed": request.headers.get("origin") in cors_origins,
        "cors_origins": cors_origins,
        "environment": "production" if is_production else "development"
    } 