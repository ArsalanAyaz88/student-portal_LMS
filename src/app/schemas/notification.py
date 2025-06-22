# File: app/schemas/notification.py
from pydantic import BaseModel
from datetime import datetime
import uuid
from typing import Optional

class NotificationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    details: str
    timestamp: datetime

    class Config:
        from_attributes = True

class AdminNotificationRead(NotificationRead):
    """
    A richer notification model for the admin panel, including an
    extracted course_id if available.
    """
    course_id: Optional[uuid.UUID] = None
