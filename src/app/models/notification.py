# File: app/models/notification.py
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time

class Notification(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(nullable=False)
    course_id: uuid.UUID = Field(nullable=False)
    event_type: str
    details: str
    timestamp: datetime = Field(default_factory=get_pakistan_time)
