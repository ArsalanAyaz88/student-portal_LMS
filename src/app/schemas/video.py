# File: app/schemas/video.py
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
from src.app.schemas.quiz import QuizRead

# Base schema with common fields
class VideoBase(BaseModel):
    title: str = Field(..., example="Introduction to FastAPI")
    description: Optional[str] = Field(default=None, example="A quick overview of the FastAPI framework.")
    url: str = Field(..., example="https://res.cloudinary.com/demo/video/upload/dog.mp4")
    duration: Optional[float] = Field(default=None, example=360.5)
    is_preview: bool = Field(default=False)

# Schema for creating a new video
class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    url: str # This will be the Cloudinary URL
    public_id: Optional[str] = None # Cloudinary public ID
    duration: Optional[float] = None
    course_id: uuid.UUID

# Schema for updating an existing video
class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    public_id: Optional[str] = None
    duration: Optional[float] = None
    is_preview: Optional[bool] = None

# Schema for reading video data (e.g., in API responses)
class VideoRead(VideoBase):
    id: uuid.UUID
    course_id: uuid.UUID
    quiz_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True

# Schema for reading video data for the admin panel
class VideoAdminRead(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    url: str

    class Config:
        from_attributes = True

# Schema for video with student's progress
class VideoWithProgress(VideoBase):
    id: uuid.UUID
    course_id: uuid.UUID
    quiz_id: Optional[uuid.UUID] = None
    watched: bool = False
    quiz_status: Optional[str] = None  # 'passed', 'failed', or 'not_taken'
    is_accessible: bool = True
    is_next_available: bool = False