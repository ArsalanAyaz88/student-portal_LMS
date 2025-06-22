# File: app/schemas/video.py
from pydantic import BaseModel, Field
from typing import Optional
import uuid

class VideoBase(BaseModel):
    youtube_url: str
    title: Optional[str] = None
    description: Optional[str] = None

class VideoCreate(VideoBase):
    pass

class VideoUpdate(VideoBase):
    youtube_url: Optional[str] = None

class VideoRead(VideoBase):
    id: uuid.UUID
    course_id: uuid.UUID

    class Config:
        from_attributes = True
