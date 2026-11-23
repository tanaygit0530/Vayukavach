from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness check. Reports database reachability without failing the endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health must never raise
        database = "unreachable"
    return {"status": "ok", "database": database, "time": datetime.now(UTC).isoformat()}
