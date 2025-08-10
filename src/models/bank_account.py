# File: app/models/bank_account.py
from sqlmodel import SQLModel, Field
import uuid

class BankAccount(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_name: str
    account_number: str
    bank_name: str
    is_active: bool = Field(default=True) 