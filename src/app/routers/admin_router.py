# File: app/routers/admin_router.py
from fastapi import APIRouter
from ..controllers import admin_controller

router = APIRouter()
router.include_router(admin_controller.router)
