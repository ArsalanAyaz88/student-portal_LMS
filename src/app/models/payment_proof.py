# File: application/src/app/models/payment_proof.py
# File: application/src/app/models/payment_proof.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.models.enrollment import Enrollment

class PaymentProof(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    enrollment_id: uuid.UUID = Field(foreign_key="enrollment.id", nullable=False)
    proof_url: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    enrollment: "src.app.models.enrollment.Enrollment" = Relationship(back_populates="payment_proofs")
