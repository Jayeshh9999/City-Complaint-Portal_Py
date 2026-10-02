from fastapi import APIRouter

from app.api.routes import admin, auth, categories, complaints, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(categories.router)
api_router.include_router(complaints.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
