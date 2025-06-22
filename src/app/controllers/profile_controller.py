# File: application/src/app/controllers/profile_controller.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import Session, select
import shutil, os
from uuid import uuid4
from ..models.profile import Profile
from ..schemas.profile import ProfileRead, ProfileUpdate
from ..db.session import get_db
from ..utils.dependencies import get_current_user
from ..utils.file import save_upload_and_get_url
from fastapi.logger import logger

router = APIRouter(tags=["Profile"])

@router.get("/profile", response_model=ProfileRead)
def read_profile(
    user = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile

@router.put("/profile", response_model=ProfileRead)
def update_profile(
    data: ProfileUpdate,
    user = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    user_obj = session.exec(select(type(user)).where(type(user).id == user.id)).first()
    full_name_updated = False
    avatar_updated = False
    for k, v in data.dict(exclude_unset=True).items():
        setattr(profile, k, v)
        if k == "full_name":
            full_name_updated = True
        if k == "avatar_url":
            avatar_updated = True
    if full_name_updated and user_obj:
        user_obj.full_name = profile.full_name
        session.add(user_obj)
    if avatar_updated and user_obj:
        user_obj.avatar_url = profile.avatar_url
        session.add(user_obj)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile

@router.post("/profile/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    try:
        # Upload file to B2
        url = save_upload_and_get_url(file, folder="avatars")
        
        # Update profile with new avatar URL
        profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
            
        profile.avatar_url = url
        session.add(profile)
        session.commit()
        session.refresh(profile)
        
        return {
            "message": "Profile avatar updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating avatar: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile avatar: {str(e)}"
        )
