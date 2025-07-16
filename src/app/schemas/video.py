# File: app/schemas/video.py
from pydantic import BaseModel, Field
from typing import Optional
import uuid

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

    class Config:
        from_attributes = True

class VideoWithProgress(VideoRead):
    watched: bool = False
 