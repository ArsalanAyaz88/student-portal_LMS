# File location: src/app/utils/security.py
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Response
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def set_auth_cookie(response: Response, token: str) -> Response:
    """
    Set the authentication cookie with secure attributes.
    
    Args:
        response: FastAPI Response object
        token: JWT token to be stored in the cookie
        
    Returns:
        Response: The modified response with cookie set
    """
    cookie_kwargs = {
        "key": "access_token",
        "value": token,
        "httponly": True,
        "max_age": 60 * 60 * 24 * 7,  # 7 days
        "samesite": "none" if IS_PRODUCTION else "lax",
        "secure": IS_PRODUCTION,  # Only send over HTTPS in production
        "path": "/",
    }
    
    # Only set domain in production
    if IS_PRODUCTION and COOKIE_DOMAIN:
        cookie_kwargs["domain"] = COOKIE_DOMAIN
    
    response.set_cookie(**cookie_kwargs)
    
    # Add CORS headers
    response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
