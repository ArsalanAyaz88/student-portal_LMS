# File: app/models/oauth.py
from sqlmodel import SQLModel, Field, Relationship
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.models.user import User

class OAuthAccount(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True)
    provider: str = Field(nullable=False, description="e.g. 'google'")
    provider_account_id: str = Field(nullable=False, description="Google sub")
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None

    user: "src.app.models.user.User" = Relationship(back_populates="oauth_accounts")
