from fastapi import APIRouter

from app.api.v1 import air, alerts, chat, finder, heat, places, reports, weather

router = APIRouter(prefix="/api/v1")
for module in (places, air, weather, heat, reports, finder, chat, alerts):
    router.include_router(module.router)
