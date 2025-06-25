# File location: src/app/utils/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.utils.security import decode_access_token

# This scheme will handle extracting the token from the Authorization header.
# The tokenUrl points to the login endpoint, which is essential for OpenAPI docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Dependency to get the current user from a JWT token.
    1. Depends on oauth2_scheme to get the token string from the header.
    2. Decodes the token to get the user_id.
    3. Retrieves the user from the database.
    4. Raises HTTPException for any errors.
    """
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: user_id missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:  # Catches errors from decode_access_token (e.g., expired, invalid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return user

async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency to get the current user and verify they are an admin.
    1. Depends on get_current_user to get the authenticated user.
    2. Checks if the user's role is 'admin'.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin access required.",
        )
    return current_user