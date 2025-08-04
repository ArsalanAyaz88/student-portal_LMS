# File: application/src/app/models/payment_proof.py
from sqlmodel import SQLModel, Field, Relationship, Column, Enum
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time
from typing import TYPE_CHECKING
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from src.app.models.enrollment import Enrollment

class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class PaymentProof(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    enrollment_id: uuid.UUID = Field(foreign_key="enrollment.id", nullable=False)
    proof_url: str
    submitted_at: datetime = Field(default_factory=get_pakistan_time)
    status: PaymentStatus = Field(sa_column=Column(Enum(PaymentStatus)), default=PaymentStatus.PENDING, nullable=False)

    enrollment: "src.app.models.enrollment.Enrollment" = Relationship(back_populates="payment_proofs")
