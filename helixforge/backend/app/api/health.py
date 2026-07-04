from __future__ import annotations

import time as _t
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout

from fastapi import APIRouter, Query

from app.adapters import registry as reg
from app.config import get_settings
from app.models.schemas import HealthStatus, ToolHealth, utcnow

router = APIRouter(prefix="/api", tags=["health"])

# Tools whose health_check() performs a network call.
NETWORK_TOOL_IDS = {"pubmed", "clinicaltrials", "chembl"}
# Tools whose deep check is expensive (dataset load / fixture run) — skipped
# unless mode=deep is explicitly requested.
DEEP_TOOL_IDS = {"tdc", "vina", "reinvent"}


@router.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "service": s.app_name, "version": s.app_version,
            "environment": s.environment, "time": utcnow()}


def _local_health(adapter) -> dict:
    """Local-only check: NEVER touches the network. Reports dependency/config
    readiness for a tool without probing external endpoints."""
    s = get_settings()
    tid = getattr(adapter, "id", "?")
    base = {"tool_id": tid, "name": getattr(adapter, "name", "?"),
            "category": getattr(adapter, "category", ""), "mode": getattr(adapter, "mode", "real"),
            "required_config": getattr(adapter, "required_config", []),
            "checked_at": utcnow(), "network_used": False, "probe_mode": "local", "last_error": ""}
    if tid in NETWORK_TOOL_IDS:
        cfg = []
        if tid == "pubmed":
            cfg = [f"NCBI_EMAIL={'set' if s.ncbi_email else 'unset'}", f"NCBI_API_KEY={'set' if s.ncbi_api_key else 'unset'}"]
        base.update(status=HealthStatus.AVAILABLE.value,
                    detail="HTTP client ready; network NOT probed (local mode)." + (" " + ", ".join(cfg) if cfg else ""))
        return base
    # Local tools (rdkit/tdc/vina/reinvent/safety/report): their health_check is
    # already local (import / binary / config), so run it.
    try:
        h: ToolHealth = adapter.health_check()
        d = h.model_dump()
        d.update(network_used=False, probe_mode="local", last_error="")
        return d
    except Exception as exc:
        base.update(status=HealthStatus.ERROR.value, detail="local health check raised", last_error=str(exc)[:200])
        return base


def _network_probe(adapter, timeout_s: float, mode: str) -> dict:
    """Run health_check() (may touch the network) with a hard timeout."""
    t0 = _t.time()
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(adapter.health)
        try:
            h: ToolHealth = fut.result(timeout=timeout_s)
            d = h.model_dump()
            d.update(latency_ms=round((_t.time() - t0) * 1000, 1), last_error="",
                     network_used=getattr(adapter, "id", "") in NETWORK_TOOL_IDS, probe_mode=mode)
            return d
        except FTimeout:
            return {"tool_id": getattr(adapter, "id", "?"), "name": getattr(adapter, "name", "?"),
                    "category": getattr(adapter, "category", ""), "status": HealthStatus.DEGRADED.value,
                    "mode": "real", "detail": f"health check exceeded {timeout_s}s (partial result)",
                    "required_config": [], "checked_at": utcnow(),
                    "latency_ms": round((_t.time() - t0) * 1000, 1), "last_error": "timeout",
                    "network_used": True, "probe_mode": mode}
        except Exception as exc:
            return {"tool_id": getattr(adapter, "id", "?"), "name": getattr(adapter, "name", "?"),
                    "category": getattr(adapter, "category", ""), "status": HealthStatus.ERROR.value,
                    "mode": "real", "detail": "health check raised", "required_config": [],
                    "checked_at": utcnow(), "latency_ms": round((_t.time() - t0) * 1000, 1),
                    "last_error": str(exc)[:200], "network_used": False, "probe_mode": mode}


@router.get("/tools/health")
def tools_health(
    mode: str = Query(default="local", pattern="^(local|live|deep)$",
                      description="local = no network; live = minimal network probe; deep = expensive checks"),
    live: bool | None = Query(default=None, description="legacy: true→live, false→local (overridden by mode)"),
    timeout_seconds: float = Query(default=5.0, ge=0.5, le=30.0),
):
    # Backward compatibility: honor the old `live` flag if `mode` left default.
    if live is not None and mode == "local":
        mode = "live" if live else "local"

    tools = []
    for a in reg.ALL:
        if mode == "local":
            d = _local_health(a)
            d.setdefault("latency_ms", 0.0)
        else:
            # deep gets a longer timeout for expensive tools; live keeps it tight.
            t = timeout_seconds if not (mode == "deep" and getattr(a, "id", "") in DEEP_TOOL_IDS) else max(timeout_seconds, 25.0)
            d = _network_probe(a, t, mode)
        d["live_probe"] = mode != "local"
        tools.append(d)

    summary: dict[str, int] = {}
    for t in tools:
        summary[t["status"]] = summary.get(t["status"], 0) + 1
    network_used = any(t.get("network_used") for t in tools)
    return {"checked_at": utcnow(), "mode": mode, "network_used": network_used,
            "timeout_seconds": timeout_seconds, "summary": summary, "tools": tools}
