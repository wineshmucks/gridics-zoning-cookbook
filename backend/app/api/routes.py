"""Top-level API router composition."""

from fastapi import APIRouter

from app.api.agentic import router as agentic_router
from app.api.letters import router as letters_router
from app.api.shared import router as shared_router

api_router = APIRouter()
api_router.include_router(shared_router)
api_router.include_router(letters_router)
api_router.include_router(agentic_router)
