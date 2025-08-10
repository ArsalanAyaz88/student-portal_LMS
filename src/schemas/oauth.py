# File: app/schemas/oauth.py
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

class GoogleToken(BaseModel):
    access_token: str
    id_token: str
    expires_in: int
    token_type: str

class GoogleUserInfo(BaseModel):
    sub: str  # Google user ID
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None

class OAuthResponse(BaseModel):
    message: str
    access_token: str
    user_id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None 