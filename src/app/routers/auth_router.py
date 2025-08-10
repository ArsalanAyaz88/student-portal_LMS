# File: app/routers/auth_router.py
# File location: src/app/routers/auth_router.py
from fastapi import APIRouter
from src.app.controllers import auth_controller

router = APIRouter(tags=["Authentication"])
router.include_router(auth_controller.router)