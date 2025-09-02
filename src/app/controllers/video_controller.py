# File: app/controllers/video_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
import uuid

from src.app.db.session import get_db
from src.app.models.user import User
from src.app.models.video import Video
from src.app.models.course import Course
from src.app.schemas.video import VideoCreate, VideoRead, VideoUpdate, VideoAdminRead
from src.app.utils.dependencies import get_current_user, get_current_admin_user

router = APIRouter() 

@router.post("/courses/{course_id}/videos", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
def create_video(video: VideoCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    logging.info(f"Attempting to create video with payload: {video.model_dump_json()}")
    """
    Create a new video and associate it with a course.
    """
    # Check if the course exists
    course = db.get(Course, video.course_id)
    if not course:
        logging.error(f"Course not found with ID: {video.course_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    db_video = Video.model_validate(video)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    logging.info(f"Successfully created video with ID: {db_video.id} for course ID: {video.course_id}")
    return db_video

@router.get("/videos") 
def get_videos_for_course(course_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """
    Get all videos for a specific course, ensuring all URL fields are returned.
    """
    videos = db.query(Video).filter(Video.course_id == course_id).order_by(Video.order).all()
    return videos

@router.put("/videos/{video_id}", response_model=VideoRead)
def update_video(video_id: uuid.UUID, video: VideoUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """
    Update a video's details.
    """
    db_video = db.get(Video, video_id)
    if not db_video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    video_data = video.model_dump(exclude_unset=True)
    for key, value in video_data.items():
        setattr(db_video, key, value)

    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """
    Delete a video.
    """
    db_video = db.get(Video, video_id)
    if not db_video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    db.delete(db_video)
    db.commit()
    return
