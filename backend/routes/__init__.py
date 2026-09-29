from fastapi import APIRouter

from .ai_copilot import router as ai_copilot_router
from .auth import router as auth_router
from .deals import router as deals_router
from .dashboard import router as dashboard_router
from .intelligence import router as intelligence_router
from .learning import router as learning_router
from .interactions import router as interactions_router
from .hindsight_intelligence import router as hindsight_intelligence_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(deals_router)
api_router.include_router(interactions_router)
api_router.include_router(hindsight_intelligence_router)
api_router.include_router(ai_copilot_router)
api_router.include_router(intelligence_router)
api_router.include_router(learning_router)

__all__ = ["api_router"]
