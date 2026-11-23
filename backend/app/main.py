from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import get_settings

app = FastAPI(
    title="VayuKavach API",
    version="0.1.0",
    description="Air quality, data completeness and heat risk for every Indian district.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
