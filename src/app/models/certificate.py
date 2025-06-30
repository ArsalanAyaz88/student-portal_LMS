from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time

class Certificate(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID
    course_id: uuid.UUID
    file_path: str
    issued_at: str = Field(default_factory=lambda: get_pakistan_time().isoformat())
    certificate_number: str  # Unique certificate number for verification 