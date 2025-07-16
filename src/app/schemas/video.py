# File: app/schemas/video.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from src.app.schemas.quiz import QuizRead

class VideoBase(BaseModel):
    cloudinary_url: str
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    is_preview: bool = False

class VideoCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None  

class VideoUpdate(VideoBase):
    cloudinary_url: Optional[str] = None

class VideoRead(VideoBase):
    id: uuid.UUID
    course_id: uuid.UUID
    quiz_id: Optional[uuid.UUID] = None
    quiz: Optional[QuizRead] = None

    class Config:
        from_attributes = True

class VideoWithProgress(VideoRead):
    watched: bool = False
    quiz_passed: bool = False
    is_accessible: bool = False
    is_next_available: bool = False
    next_video_id: Optional[uuid.UUID] = None
    required_quiz_passed: bool = True  # Whether the previous quiz needs to be passed
    previous_quiz_passed: bool = True  # Whether the previous quiz was passed
    
    # This will inherit quiz field from VideoRead