"""Collects every v1 router under the /api/v1 prefix."""

from fastapi import APIRouter

from app.api.v1 import auth, boards, collaboration, tasks, users, workspaces

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(boards.router)
api_router.include_router(tasks.router)
api_router.include_router(collaboration.router)
