# File: application/src/app/models/payment.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .enrollment import EnrollmentApplication

class Payment(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    enrollment_id: uuid.UUID = Field(foreign_key="enrollment.id")
    amount: float
    currency: str = Field(default="USD")
    status: str = Field(default="initiated")
    initiated_at: datetime = Field(default_factory=get_pakistan_time)
    verified_at: Optional[datetime] = None

class PaymentProof(SQLModel, table=True):
    __tablename__ = "paymentproof"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    transaction_id: str
    proof_url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_verified: bool = Field(default=False)

    # Foreign key for the bank account paid to
    bank_account_id: uuid.UUID = Field(foreign_key="bank_accounts.id")

    # Foreign key to link back to the application
    application_id: uuid.UUID = Field(foreign_key="enrollment_applications.id")
    
    # Relationship to the application


