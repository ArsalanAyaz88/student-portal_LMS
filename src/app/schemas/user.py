# File location: src/app/schemas/user.py
from pydantic import BaseModel, EmailStr
import uuid
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool

    class Config: 
        from_attributes = True
