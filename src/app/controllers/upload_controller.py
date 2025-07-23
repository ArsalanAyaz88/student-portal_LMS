# File: src/app/controllers/upload_controller.py
import cloudinary
import cloudinary.utils
import os
import time
from fastapi import APIRouter, Depends, HTTPException

from ..utils.dependencies import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/uploads",
    tags=["Uploads"]
)

# It's assumed that Cloudinary config is loaded globally on app startup.
# If not, you might need to call cloudinary.config() here using environment variables.

@router.post("/signature")
async def get_upload_signature(current_user: User = Depends(get_current_user)):
    """
    Generate a signature for a direct, signed upload to Cloudinary.
    """
    # Ensure Cloudinary is configured
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")

    if not all([api_secret, api_key, cloud_name]):
        raise HTTPException(
            status_code=500,
            detail="Cloudinary is not configured on the server. Missing environment variables."
        )

    timestamp = int(time.time())
    # Parameters to sign. The frontend MUST use these exact same parameters in the upload request.
    # You can add more parameters here like upload_preset, public_id, etc.
    params_to_sign = {"timestamp": timestamp}

    try:
        # Generate the signature
        signature = cloudinary.utils.api_sign_request(params_to_sign, api_secret)
        return {
            "signature": signature,
            "timestamp": timestamp,
            "api_key": api_key,
            "cloud_name": cloud_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload signature: {e}")
