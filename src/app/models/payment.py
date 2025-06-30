# File: application/src/app/models/payment.py
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time
from typing import Optional

class Payment(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    enrollment_id: uuid.UUID = Field(foreign_key="enrollment.id")
    amount: float
    currency: str = Field(default="USD")
    status: str = Field(default="initiated")
    initiated_at: datetime = Field(default_factory=get_pakistan_time)
    verified_at: Optional[datetime] = None
