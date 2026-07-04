from __future__ import annotations

from fastapi import APIRouter

from app.adapters import registry as reg
from app.config import get_settings
from app.models.schemas import utcnow

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "service": s.app_name,
        "version": s.app_version,
        "environment": s.environment,
        "time": utcnow(),
    }


@router.get("/tools/health")
def tools_health():
    healths = reg.health_all()
    summary = {"AVAILABLE": 0, "MISSING_DEPENDENCY": 0, "NOT_CONFIGURED": 0, "DEGRADED": 0, "ERROR": 0}
    for h in healths:
        summary[h.status.value] = summary.get(h.status.value, 0) + 1
    return {"checked_at": utcnow(), "summary": summary, "tools": [h.model_dump() for h in healths]}
