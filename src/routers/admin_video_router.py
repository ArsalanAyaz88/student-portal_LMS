# File: app/routers/admin_video_router.py
from fastapi import APIRouter
from src.app.controllers import video_controller

router = APIRouter()

# Include the video controller router
router.include_router(video_controller.router, prefix="/admin", tags=["Admin Videos"])
