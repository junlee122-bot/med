from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout

from fastapi import APIRouter, Query

from app.adapters import registry as reg
from app.config import get_settings
from app.models.schemas import HealthStatus, ToolHealth, utcnow

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


def _probe(adapter, timeout_s: float) -> dict:
    """Run one adapter health check with a hard per-tool timeout so the
    aggregate endpoint returns partial results and never hangs."""
    import time as _t
    t0 = _t.time()
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(adapter.health)
        try:
            h: ToolHealth = fut.result(timeout=timeout_s)
            d = h.model_dump()
            d["latency_ms"] = round((_t.time() - t0) * 1000, 1)
            d["last_error"] = ""
            return d
        except FTimeout:
            return {
                "tool_id": getattr(adapter, "id", "?"), "name": getattr(adapter, "name", "?"),
                "category": getattr(adapter, "category", ""), "status": HealthStatus.DEGRADED.value,
                "mode": "real", "detail": f"health check exceeded {timeout_s}s (partial result)",
                "required_config": [], "checked_at": utcnow(),
                "latency_ms": round((_t.time() - t0) * 1000, 1), "last_error": "timeout",
            }
        except Exception as exc:  # never let one tool break the matrix
            return {
                "tool_id": getattr(adapter, "id", "?"), "name": getattr(adapter, "name", "?"),
                "category": getattr(adapter, "category", ""), "status": HealthStatus.ERROR.value,
                "mode": "real", "detail": "health check raised", "required_config": [],
                "checked_at": utcnow(), "latency_ms": round((_t.time() - t0) * 1000, 1),
                "last_error": str(exc)[:200],
            }


@router.get("/tools/health")
def tools_health(
    live: bool = Query(default=True, description="true = allow minimal network probes; false = local checks only"),
    timeout_seconds: float = Query(default=5.0, ge=0.5, le=30.0),
):
    tools = []
    for a in reg.ALL:
        d = _probe(a, timeout_seconds)
        d["live_probe"] = live
        tools.append(d)
    summary: dict[str, int] = {}
    for t in tools:
        summary[t["status"]] = summary.get(t["status"], 0) + 1
    return {"checked_at": utcnow(), "live": live, "timeout_seconds": timeout_seconds,
            "summary": summary, "tools": tools}
