# File: application/src/app/models/payment_proof.py
from sqlmodel import SQLModel, Field, Relationship, Column, Enum
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time
from typing import TYPE_CHECKING, Optional
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from .enrollment import Enrollment

class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class PaymentProofBase(SQLModel):
    proof_url: str
    submitted_at: datetime = Field(default_factory=get_pakistan_time)
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, sa_column=Column(Enum(PaymentStatus), nullable=False))

class PaymentProof(PaymentProofBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    enrollment_id: uuid.UUID = Field(foreign_key="enrollment.id")
    enrollment: "Enrollment" = Relationship(back_populates="payment_proofs")
    enrollment_application_id: uuid.UUID = Field(foreign_key="enrollment_application.id")
    enrollment_application: "EnrollmentApplication" = Relationship(back_populates="payment_proof")
