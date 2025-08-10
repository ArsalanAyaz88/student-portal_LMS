# File location: src/app/utils/oauth.py
import os
import httpx
from dotenv import load_dotenv
from ..schemas.oauth import GoogleToken, GoogleUserInfo
from ..utils.security import create_access_token

load_dotenv()
 
# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI") 

async def get_google_token(code: str) -> GoogleToken:
    """Exchange authorization code for Google tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return GoogleToken(**response.json())

async def get_google_user_info(access_token: str) -> GoogleUserInfo:
    """Get user info from Google using access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return GoogleUserInfo(**response.json())

def create_oauth_response(user, access_token: str):
    """Create standardized OAuth response."""
    return {
        "message": "Successfully authenticated with Google",
        "access_token": access_token,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
    }
