from fastapi import APIRouter
from src.app.controllers import enrollment_controller

router = APIRouter()
router.include_router(enrollment_controller.router)