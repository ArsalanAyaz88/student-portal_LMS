# File: app/models/profile.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

class Profile(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

    user: "User" = Relationship(back_populates="profile")
