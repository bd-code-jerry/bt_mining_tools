from fastapi import APIRouter

from .features.auth.router import router as auth_router
from .features.balances.router import router as balances_router
from .features.preferences.router import router as preferences_router
from .features.total_balances.router import router as total_balances_router
from .features.usage.router import router as usage_router
from .features.users.router import router as users_router
from .features.workspaces.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(preferences_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
api_router.include_router(balances_router)
api_router.include_router(usage_router)
api_router.include_router(total_balances_router)
