from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session
from typing import List, Optional
import logging
from uuid import UUID
import os

from ..db.session import get_db
from ..models.video import Video
from ..models.course import Course
from ..schemas.video import VideoRead, VideoCreate, VideoUpdate
from ..utils.dependencies import get_current_admin_user
from ..utils.file import save_upload_and_get_url
from ..models.user import User

router = APIRouter(
    prefix="/api/v1",
    tags=["videos"]
)

@router.post("/courses/{course_id}/videos", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
async def upload_course_video(
    course_id: UUID,
    video_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Upload a video for a specific course.
    
    - **course_id**: ID of the course to add the video to
    - **video_file**: The video file to upload (MP4, MOV, etc.)
    - **title**: Optional title for the video (defaults to filename)
    - **description**: Optional description for the video
    """
    # Verify course exists
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
    if video_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Supported types: {', '.join([t.split('/')[-1] for t in allowed_types])}"
        )
    
    try:
        # Upload to Cloudinary
        folder = f"courses/{course_id}/videos"
        video_url = await save_upload_and_get_url(file=video_file, folder=folder)
        
        # Create video record
        video = Video(
            course_id=course_id,
            cloudinary_url=video_url,
            title=title or os.path.splitext(video_file.filename)[0],
            description=description,
            is_preview=False
        )
        
        db.add(video)
        db.commit()
        db.refresh(video)
        
        return video
        
    except Exception as e:
        db.rollback()
        logging.error(f"Error uploading video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload video"
        )

@router.get("/courses/{course_id}/videos", response_model=List[VideoRead])
def list_course_videos(
    course_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    List all videos for a specific course with pagination.
    """
    # Verify course exists
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    videos = db.query(Video).filter(
        Video.course_id == course_id
    ).offset(skip).limit(limit).all()
    
    return videos

@router.patch("/videos/{video_id}", response_model=VideoRead)
def update_video(
    video_id: UUID,
    video_update: VideoUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Update video metadata (title, description, etc.)
    """
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # Update only the fields that were provided
    update_data = video_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(video, field, value)
    
    db.commit()
    db.refresh(video)
    return video

@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Delete a video.
    Note: This only removes the database record. The actual file in Cloudinary
    should be managed separately or through Cloudinary's auto-cleanup rules.
    """
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    db.delete(video)
    db.commit()
    return {"ok": True}
