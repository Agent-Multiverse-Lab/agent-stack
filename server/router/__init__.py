from fastapi import APIRouter

from .agent_router import agent_router
from .auth_router import router as auth_router
from .knowledge_router import router as knowledge_router
from .library_router import router as library_router
from .model_router import router as model_router
from .sandbox_router import router as sandbox_router
from .thread_router import router as thread_router

api_router = APIRouter()
api_router.include_router(agent_router)
api_router.include_router(auth_router)
api_router.include_router(knowledge_router)
api_router.include_router(library_router)
api_router.include_router(model_router)
api_router.include_router(sandbox_router)
api_router.include_router(thread_router)

__all__ = ["api_router"]
