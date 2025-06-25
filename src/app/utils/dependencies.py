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
    # Try to get token from cookie first
    token = request.cookies.get("access_token")
    
    # If not in cookie, check Authorization header
    if not token and "authorization" in request.headers:
        auth_header = request.headers["authorization"]
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    print(f"[LOG] Access token (admin): {token}")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - No token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Remove 'Bearer ' prefix if present (both from cookie and header)
    token = token.replace("Bearer ", "").strip()
    
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Check if user is an admin
        if user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return user
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions with proper headers
        raise http_exc
    except Exception as e:
        # Handle other exceptions (like JWT decode errors)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )