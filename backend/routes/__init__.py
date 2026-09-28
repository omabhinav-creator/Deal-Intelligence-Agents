from fastapi import APIRouter

from .ai_copilot import router as ai_copilot_router
from .deals import router as deals_router
from .intelligence import router as intelligence_router
from .interactions import router as interactions_router

api_router = APIRouter()
api_router.include_router(deals_router)
api_router.include_router(interactions_router)
api_router.include_router(ai_copilot_router)
api_router.include_router(intelligence_router)

__all__ = ["api_router"]