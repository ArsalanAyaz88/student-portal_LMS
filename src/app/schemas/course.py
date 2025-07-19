# File: app/schemas/course.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid
from src.app.schemas.video import VideoRead

class CourseBase(BaseModel):
    title: str = Field(..., example="The Complete Web Development Bootcamp")
    description: str = Field(..., example="Learn to build modern web applications from scratch.")
    price: float = Field(..., example=19.99)
    thumbnail_url: Optional[str] = Field(default=None, example="https://example.com/images/thumbnail.png")
    difficulty_level: Optional[str] = Field(default=None, example="Intermediate")
    outcomes: Optional[str] = Field(default="", example="Build and deploy a full-stack web application.")
    prerequisites: Optional[str] = Field(default="", example="Basic HTML and CSS knowledge.")
    curriculum: Optional[str] = Field(default="", example="1. HTML\n2. CSS\n3. JavaScript\n4. React\n5. Node.js")

class CourseCreate(CourseBase):
    pass

class CourseCreateAdmin(CourseBase):
    """Schema for creating a course by admin with additional fields"""
    # created_by is set automatically from the current admin user
    status: str = "active"

    class Config:
        from_attributes = True

class CourseUpdate(CourseBase):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

class CourseRead(BaseModel):
    """Simplified course read schema with only essential fields"""
    id: uuid.UUID
    title: str
    thumbnail_url: Optional[str] = None
    expiration_date: Optional[datetime] = None

    class Config:
        from_attributes = True

class CourseListRead(CourseRead):
    total_enrollments: int = 0
    active_enrollments: int = 0
    average_progress: float = 0.0

class CourseExploreList(BaseModel):
    id: uuid.UUID
    title: str
    price: float
    thumbnail_url: Optional[str] = None

class CourseExploreDetail(CourseBase):
    id: uuid.UUID

class CourseCurriculumDetail(BaseModel):
    curriculum: str

class CourseDetail(CourseRead):
    videos: List[VideoRead] = []

class CourseBasicDetail(BaseModel):
    id: uuid.UUID
    title: str
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True

class DescriptionSchema(BaseModel):
    description: str

class OutcomesSchema(BaseModel):
    outcomes: str

class PrerequisitesSchema(BaseModel):
    prerequisites: str

class CurriculumSchema(BaseModel):
    curriculum: str

class CourseProgress(BaseModel):
    completed_videos: int
    total_videos: int
    progress_percentage: float

class AdminCourseStats(BaseModel):
    """Schema for course statistics in admin panel"""
    total_enrollments: int = Field(..., description="Total number of enrollments")
    active_enrollments: int = Field(..., description="Number of active enrollments")
    completed_enrollments: int = Field(..., description="Number of completed enrollments")
    average_progress: float = Field(..., description="Average course progress percentage")
    total_revenue: float = Field(..., description="Total revenue from the course")
    last_updated: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True

class AdminCourseList(BaseModel):
    """Schema for course list in admin panel"""
    id: uuid.UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Course title")
    price: float = Field(..., description="Course price")
    total_enrollments: int = Field(..., description="Total number of enrollments")
    active_enrollments: int = Field(..., description="Number of active enrollments")
    average_progress: float = Field(..., description="Average course progress")
    status: str = Field(..., description="Course status (active/inactive)")
    created_at: datetime = Field(..., description="Course creation date")
    updated_at: datetime = Field(..., description="Last update date")

    class Config:
        from_attributes = True

class AdminCourseDetail(BaseModel):
    """Schema for detailed course information in admin panel"""
    id: uuid.UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Course title")
    description: str = Field(..., description="Course description")
    price: float = Field(..., description="Course price")
    thumbnail_url: Optional[str] = Field(None, description="Course thumbnail URL")
    difficulty_level: Optional[str] = Field(None, description="Course difficulty level")
    created_by: str = Field(..., description="Course creator")
    updated_by: str = Field(..., description="Last updater")
    created_at: datetime = Field(..., description="Course creation date")
    updated_at: datetime = Field(..., description="Last update date")
    status: str = Field(..., description="Course status")

    class Config:
        from_attributes = True
