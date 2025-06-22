from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime

class Certificate(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID
    course_id: uuid.UUID
    file_path: str
    issued_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    certificate_number: str  # Unique certificate number for verification 