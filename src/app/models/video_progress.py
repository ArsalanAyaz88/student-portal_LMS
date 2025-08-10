from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import Column, String, Boolean, UUID

if TYPE_CHECKING:
    from src.app.models.video import Video
    from src.app.models.user import User

class VideoProgress(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    video_id: uuid.UUID = Field(foreign_key="video.id", nullable=False)
    completed: bool = Field(default=False)

    video: "src.app.models.video.Video" = Relationship(back_populates="progress")
    user: "src.app.models.user.User" = Relationship(back_populates="video_progress")
