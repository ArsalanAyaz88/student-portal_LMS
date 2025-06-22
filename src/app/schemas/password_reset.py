# File: app/schemas/password_reset.py
from pydantic import BaseModel, EmailStr, constr
from typing import Literal

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    message: str
    status: Literal["not_found", "sent"]

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    pin: constr(min_length=6, max_length=6)
    new_password: str

class ResetPasswordResponse(BaseModel):
    message: str
    status: Literal["success"]
