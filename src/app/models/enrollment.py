# File: app/models/enrollment.py
from sqlmodel import SQLModel, Field, Relationship, JSON
import uuid
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING, List
from pydantic import validator
import pytz
from src.app.utils.time import get_pakistan_time, convert_to_pakistan_time

if TYPE_CHECKING:
    from src.app.models.user import User
    from src.app.models.course import Course
    from src.app.models.payment_proof import PaymentProof

import uuid

class Enrollment(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    course_id: uuid.UUID = Field(foreign_key="course.id")
    status: str = Field(default="pending")  # pending, approved, rejected
    enroll_date: datetime = Field(default_factory=get_pakistan_time)
    expiration_date: Optional[datetime] = None
    is_accessible: bool = Field(default=False)
    days_remaining: Optional[int] = None
    audit_log: list = Field(sa_type=JSON, default_factory=list)
    last_access_date: Optional[datetime] = None

    @validator('enroll_date', 'expiration_date', 'last_access_date', pre=True)
    def validate_timezone(cls, v):
        """Ensure all datetime fields are timezone-aware and in Pakistan time"""
        if v is None:
            return v
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        return convert_to_pakistan_time(v)

    user: "User" = Relationship(back_populates="enrollments")
    course: "Course" = Relationship(back_populates="enrollments")
    payment_proofs: List["PaymentProof"] = Relationship(back_populates="enrollment", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def update_expiration_status(self):
        """Update the expiration status and days remaining"""
        current_time = get_pakistan_time()
        
        if self.expiration_date:
            # Ensure both datetimes are timezone-aware
            if self.expiration_date.tzinfo is None:
                self.expiration_date = convert_to_pakistan_time(self.expiration_date)
            
            # Calculate days remaining using timezone-aware datetimes
            time_diff = self.expiration_date - current_time
            self.days_remaining = time_diff.days
            
            # Update is_accessible based on expiration
            self.is_accessible = time_diff.total_seconds() > 0
        else:
            self.days_remaining = None
            self.is_accessible = True
        self.last_access_date = current_time