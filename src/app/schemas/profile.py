# File location: src/app/schemas/profile.py
from pydantic import BaseModel
import uuid
from typing import Optional

class ProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]

    class Config:
        orm_mode = True

class ProfileUpdate(BaseModel):
    full_name: Optional[str]
    bio: Optional[str]
