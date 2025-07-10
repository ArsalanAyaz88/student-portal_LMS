from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime
from src.app.utils.time import get_pakistan_time

class Certificate(SQLModel, table=True):
    student_name: str = Field(index=True)
    __table_args__ = {"extend_existing": True}
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID
    course_id: uuid.UUID
    file_path: str
    issued_at: datetime = Field(default_factory=get_pakistan_time)
    certificate_number: str  # Unique certificate number for verification 