from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.ratelimit import RateLimitMiddleware
from app.api.v1 import router as v1_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="VayuKavach API",
    version="0.1.0",
    description=(
        "Air quality, data completeness and heat risk for Indian districts. Every response "
        "carries `source`, `updated_at` (IST), `label` (measured or estimated) and `stale`. "
        "Data: CPCB via data.gov.in, OpenAQ, Open-Meteo and CAMS (CC BY 4.0)."
    ),
)

app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(v1_router)
