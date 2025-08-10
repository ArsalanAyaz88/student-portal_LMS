from fastapi import APIRouter
from src.app.controllers import admin_controller

router = APIRouter()
router.include_router(admin_controller.router)
