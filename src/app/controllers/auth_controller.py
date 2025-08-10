# File: application/src/app/controllers/auth_controller.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from datetime import datetime, timedelta
from random import randint
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuthError
import os
from uuid import uuid4
from src.app.models.profile import Profile

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.password_reset import PasswordReset
from src.app.models.oauth import OAuthAccount
from src.app.schemas.user import UserCreate, UserRead
from src.app.schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from src.app.schemas.oauth import OAuthResponse
from src.app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)
from src.app.utils.email import send_reset_pin_email
from src.app.utils.oauth import (
    get_google_token,
    get_google_user_info,
    create_oauth_response,
    GOOGLE_CLIENT_ID,
    GOOGLE_REDIRECT_URI
)
import logging

router = APIRouter()

@router.post("/signup", response_model=UserRead)
def signup(
    user: UserCreate,
    session: Session = Depends(get_db)
):
    existing = session.exec(
        select(User).where(User.email == user.email)
    ).first()
    if existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Email already registered"
        )

    # 1️⃣ Create the User
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password)
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # 2️⃣ Create a blank Profile for them
    profile = Profile(
        user_id=new_user.id,
        full_name=None,
        avatar_url=None,
        bio=None
    )
    session.add(profile)
    session.commit()

    return new_user

@router.post("/admin-login")
async def admin_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db)
):
    print("--- ADMIN LOGIN FUNCTION STARTED ---")
    logging.info("Attempting admin login for user: %s", form_data.username)
    user = session.exec(
        select(User).where(User.email == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access the admin panel."
        )
    
    # Create access token with user info
    access_token = create_access_token({
        "user_id": str(user.id),
        "role": user.role,
        "email": user.email
    })
    
    # Log the origin for debugging
    origin = request.headers.get("origin")
    print(f"Login request from origin: {origin}")
    
    # Create the response content
    content = {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "message": "Admin login successful."
    }

    return JSONResponse(content=content)

@router.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db)
):
    logging.info(f"--- LOGIN ATTEMPT FOR USER: {form_data.username} ---")
    try:
        user = session.exec(
            select(User).where(User.email == form_data.username)
        ).first()

        if not user:
            logging.warning(f"Login failed: User '{form_data.username}' not found.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logging.info(f"User '{form_data.username}' found. Verifying password...")
        if not verify_password(form_data.password, user.hashed_password):
            logging.warning(f"Login failed: Incorrect password for user '{form_data.username}'.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logging.info(f"Password verified for '{form_data.username}'. Creating access token...")
        token = create_access_token({"user_id": str(user.id), "role": user.role})

        content = {
            "access_token": token,
            "token_type": "bearer",
            "role": user.role,
            "message": "Login successful."
        }
        
        logging.info(f"Login successful for user '{form_data.username}'.")
        return JSONResponse(content=content)

    except HTTPException as e:
        # Re-raise HTTP exceptions to be handled by FastAPI
        raise e
    except Exception as e:
        logging.error(f"An unexpected error occurred during login for {form_data.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred.",
        )

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse
)
def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db)
):
    # Check if user exists and is active
    user = session.exec(
        select(User)
        .where(User.email == request.email)
        .where(User.is_active == True)
    ).first()

    if not user:
        # Return a user-friendly message for non-existent or inactive users
        return {
            "message": "This email is not registered in our system. Please check the email address or sign up for a new account.",
            "status": "not_found"
        }

    # Generate a 6-digit PIN
    pin = f"{randint(100000, 999999)}"
    
    # Create password reset record
    reset = PasswordReset(
        user_id=user.id,
        pin=pin,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    
    # Invalidate any existing unused PINs for this user
    existing_resets = session.exec(
        select(PasswordReset)
        .where(PasswordReset.user_id == user.id)
        .where(PasswordReset.used == False)
        .where(PasswordReset.expires_at > datetime.utcnow())
    ).all()
    
    for existing in existing_resets:
        existing.used = True
        session.add(existing)
    
    # Add new reset record
    session.add(reset)
    session.commit()
    
    # Send email in background
    background_tasks.add_task(send_reset_pin_email, user.email, pin)
    
    # Return success message for valid users
    return {
        "message": "We've sent a password reset PIN to your email. Please check your inbox and spam folder.",
        "status": "sent"
    }

@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse
)
def reset_password(
    data: ResetPasswordRequest,
    session: Session = Depends(get_db)
):
    # First check if user exists
    user = session.exec(
        select(User)
        .where(User.email == data.email)
        .where(User.is_active == True)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address. Please check your email and try again."
        )
    
    # Check for valid, unused, and non-expired PIN
    reset = session.exec(
        select(PasswordReset)
        .where(
            PasswordReset.user_id == user.id,
            PasswordReset.pin == data.pin,
            PasswordReset.used == False,
            PasswordReset.expires_at >= datetime.utcnow()
        )
        .order_by(PasswordReset.created_at.desc())
    ).first()
    
    if not reset:
        # Check if PIN exists but is expired
        expired_reset = session.exec(
            select(PasswordReset)
            .where(
                PasswordReset.user_id == user.id,
                PasswordReset.pin == data.pin,
                PasswordReset.used == False,
                PasswordReset.expires_at < datetime.utcnow()
            )
        ).first()
        
        if expired_reset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The PIN has expired. Please request a new password reset PIN."
            )
        
        # Check if PIN exists but was already used
        used_reset = session.exec(
            select(PasswordReset)
            .where(
                PasswordReset.user_id == user.id,
                PasswordReset.pin == data.pin,
                PasswordReset.used == True
            )
        ).first()
        
        if used_reset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This PIN has already been used. Please request a new password reset PIN."
            )
        
        # If none of the above, PIN is invalid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PIN. Please check the PIN and try again."
        )
    
    # Update password and mark PIN as used
    user.hashed_password = hash_password(data.new_password)
    reset.used = True
    session.add(user)
    session.add(reset)
    session.commit()
    
    return {
        "message": "Your password has been successfully reset. You can now login with your new password.",
        "status": "success"
    }

@router.post("/logout")
def logout():
    # The client is responsible for deleting the token.
    return {"message": "Successfully logged out"}

@router.get("/google/login")
async def google_login():
    """Redirect to Google OAuth login page."""
    try:
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&scope=openid%20email%20profile"
        print(f"Generated auth URL: {auth_url}")  # Debug log
        return {"url": auth_url}
    except Exception as e:
        print(f"Error generating auth URL: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  
            detail=f"Error generating auth URL: {str(e)}"
        )

@router.get("/google/callback", response_model=OAuthResponse)
async def google_callback(code: str, session: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    try:
        print(f"Received callback with code: {code}")  # Debug log
        print(f"Using redirect URI: {GOOGLE_REDIRECT_URI}")  # Debug log
        
        # Get tokens from Google
        tokens = await get_google_token(code)
        print(f"Received tokens from Google")  # Debug log
        
        # Get user info from Google
        user_info = await get_google_user_info(tokens.access_token)
        print(f"Received user info: {user_info.email}")  # Debug log
        
        # Check if user exists with this email
        user = session.exec(
            select(User).where(User.email == user_info.email)
        ).first()
        
        if not user:
            # Create new user
            user = User(
                email=user_info.email,
                full_name=user_info.name,
                avatar_url=user_info.picture,
                is_active=True
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"Created new user: {user.email}")  # Debug log
        
        # Ensure profile exists for user
        profile = session.exec(
            select(Profile).where(Profile.user_id == user.id)
        ).first()
        if not profile:
            profile = Profile(
                user_id=user.id,
                full_name=user_info.name,
                avatar_url=user_info.picture
            )
            session.add(profile)
            session.commit()
            print(f"Created profile for user: {user.email}")  # Debug log
        
        # Create or update OAuth account
        oauth_account = session.exec(
            select(OAuthAccount)
            .where(OAuthAccount.provider == "google")
            .where(OAuthAccount.provider_account_id == user_info.sub)
        ).first()
        
        if not oauth_account:
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=user_info.sub,
                access_token=tokens.access_token,
                expires_at=datetime.utcnow() + timedelta(seconds=tokens.expires_in)
            )
        else:
            oauth_account.access_token = tokens.access_token
            oauth_account.expires_at = datetime.utcnow() + timedelta(seconds=tokens.expires_in)
        
        session.add(oauth_account)
        session.commit()
        
        # Create JWT token
        access_token = create_access_token({
            "user_id": str(user.id),
            "role": user.role
        })
        
        # The token is returned in the response body, client should handle it.

        # Create and return the OAuth response
        return OAuthResponse(
            message="Successfully authenticated with Google",
            access_token=access_token,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url
        )
        
    except Exception as e:
        print(f"Error in Google callback: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}"
        )
 