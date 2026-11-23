from fastapi import APIRouter

from app.api.v1 import air, heat, places, reports, weather

router = APIRouter(prefix="/api/v1")
for module in (places, air, weather, heat, reports):
    router.include_router(module.router)
