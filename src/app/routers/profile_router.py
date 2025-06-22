# File: app/routers/profile_router.py
# File location: src/app/routers/profile_router.py
from fastapi import APIRouter
from ..controllers import profile_controller

router = APIRouter()
router.include_router(profile_controller.router)