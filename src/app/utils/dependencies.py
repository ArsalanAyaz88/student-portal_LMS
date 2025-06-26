# File location: src/app/utils/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Dependency to get the current user from a JWT token provided
    in the Authorization header.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except Exception:  # Catches JWTError from decode_access_token and others
        raise credentials_exception

    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency to get the current user and verify they are an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin access required.",
        )
    return current_user