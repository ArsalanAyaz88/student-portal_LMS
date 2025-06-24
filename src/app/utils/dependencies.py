# File location: src/app/utils/dependencies.py
from fastapi import Request, Depends, HTTPException, status
from sqlmodel import Session
from src.app.db.session import get_db
from src.app.models.user import User
from src.app.utils.security import decode_access_token

async def get_current_user(
    request: Request,
    session: Session = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")
    print(f"[LOG] Access token: {token}")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(token)
    user_id: str = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or invalid user",
        )
    return user

# Dependency to check for admin user
async def get_current_admin_user(
    request: Request,
    session: Session = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")
    print(f"[LOG] Access token (admin): {token}")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(token)
    user_id: str = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = session.get(User, user_id)
    if not user or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as admin",
        )
    return user
 