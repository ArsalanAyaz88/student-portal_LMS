# File: app/routers/course_router.py
# File location: src/app/routers/course_router.py
from fastapi import APIRouter
from ..controllers import course_controller

router = APIRouter()
router.include_router(course_controller.router)