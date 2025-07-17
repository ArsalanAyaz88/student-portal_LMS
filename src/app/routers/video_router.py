from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
import logging
from uuid import UUID
import os
import json

from ..db.session import get_db
from ..models.video import Video
from ..models.course import Course
from ..models.quiz import Quiz, Question, Option
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
    quiz: Optional[str] = Form(None),  # Accept quiz data as a JSON string
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Upload a video for a specific course, optionally with a quiz.
    
    - **course_id**: ID of the course to add the video to
    - **video_file**: The video file to upload
    - **title**: Optional title for the video
    - **description**: Optional description for the video
    - **quiz**: Optional JSON string representing the quiz data
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
    if video_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {video_file.content_type}"
        )

    try:
        folder = f"courses/{course_id}/videos"
        video_url = await save_upload_and_get_url(file=video_file, folder=folder)

        quiz_id = None
        if quiz:
            try:
                quiz_data = json.loads(quiz)
                if quiz_data and quiz_data.get('questions'):
                    new_quiz = Quiz(
                        course_id=course_id,
                        title=quiz_data.get('title', 'Video Quiz'),
                        description=quiz_data.get('description'),
                    )
                    db.add(new_quiz)
                    db.flush()  # Flush to get the new_quiz.id

                    for q_data in quiz_data['questions']:
                        new_question = Question(
                            quiz_id=new_quiz.id,
                            text=q_data['text'],
                            is_multiple_choice=True
                        )
                        db.add(new_question)
                        db.flush()  # Flush to get new_question.id

                        for o_data in q_data['options']:
                            new_option = Option(
                                question_id=new_question.id,
                                text=o_data['text'],
                                is_correct=o_data['is_correct']
                            )
                            db.add(new_option)
                    
                    quiz_id = new_quiz.id

            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format for quiz data.")

        video = Video(
            course_id=course_id,
            cloudinary_url=video_url,
            title=title or os.path.splitext(video_file.filename)[0],
            description=description,
            is_preview=False,
            quiz_id=quiz_id
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
            detail=f"Failed to upload video: {str(e)}"
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

@router.patch("/videos/{video_id}/quiz/{quiz_id}", response_model=VideoRead)
async def associate_quiz_with_video(
    video_id: UUID,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Associate a quiz with a video.
    Only admins can perform this action.
    """
    # Get the video
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # Get the quiz
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    # Verify quiz belongs to the same course as video
    if quiz.course_id != video.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quiz must belong to the same course as the video"
        )
    
    # Associate quiz with video
    video.quiz_id = quiz.id
    db.add(video)
    db.commit()
    db.refresh(video)
    
    return video

@router.delete("/videos/{video_id}/quiz", response_model=VideoRead)
async def remove_quiz_from_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Remove quiz association from a video.
    Only admins can perform this action.
    """
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    video.quiz_id = None
    db.add(video)
    db.commit()
    db.refresh(video)
    
    return video

@router.get("/videos/{video_id}/quiz")
async def get_video_quiz(
    video_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Get the quiz associated with a video.
    Only admins can access this endpoint.
    """
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    if not video.quiz_id:
        return {"quiz_id": None}
    
    return {"quiz_id": video.quiz_id}
