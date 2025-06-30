# File: app/models/enrollment.py
from sqlmodel import SQLModel, Field, Relationship, JSON
import uuid
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING, List
import pytz
from src.app.utils.time import get_pakistan_time

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
    enroll_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    is_accessible: bool = Field(default=False)
    days_remaining: Optional[int] = None
    audit_log: list = Field(sa_type=JSON, default_factory=list)
    last_access_date: Optional[datetime] = None

    user: "src.app.models.user.User" = Relationship(back_populates="enrollments")
    course: "src.app.models.course.Course" = Relationship(back_populates="enrollments")
    payment_proofs: List["src.app.models.payment_proof.PaymentProof"] = Relationship(back_populates="enrollment", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def update_expiration_status(self):
        """Update the expiration status and days remaining"""
        current_time = get_pakistan_time()  # This is an aware datetime in Asia/Karachi timezone

        if self.expiration_date:
            # Assuming self.expiration_date is a naive datetime object stored in UTC.
            # We need to make it timezone-aware to compare it correctly.
            expiration_aware = pytz.utc.localize(self.expiration_date)

            # Now we can compare the two aware datetime objects
            if current_time > expiration_aware:
                # The course has expired
                self.is_accessible = False
            else:
                # The course is still accessible
                self.is_accessible = True

            # Calculate the days remaining
            time_difference = expiration_aware - current_time
            self.days_remaining = time_difference.days
        else:
            # If there's no expiration date, the course is always accessible
            self.days_remaining = None
            self.is_accessible = True

        self.last_access_date = current_time 
