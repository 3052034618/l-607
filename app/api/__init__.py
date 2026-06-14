from fastapi import APIRouter

from .auth import router as auth_router
from .sites import router as sites_router
from .transport import router as transport_router
from .vehicles import router as vehicles_router
from .enforcement import router as enforcement_router
from .penalties import router as penalties_router
from .business import router as business_router
from .notifications import router as notifications_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(sites_router)
api_router.include_router(transport_router)
api_router.include_router(vehicles_router)
api_router.include_router(enforcement_router)
api_router.include_router(penalties_router)
api_router.include_router(business_router)
api_router.include_router(notifications_router)
