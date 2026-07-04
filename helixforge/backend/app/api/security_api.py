from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import DATA_DIR
from app.models.schemas import utcnow
from app.services import security_audit

router = APIRouter(prefix="/api", tags=["security"])
CACHE_DIR = DATA_DIR / "cache"


@router.get("/security/audit")
def security_audit_endpoint():
    return security_audit.run_audit()


@router.get("/cache/stats")
def cache_stats():
    files = list(CACHE_DIR.rglob("*")) if CACHE_DIR.exists() else []
    file_list = [f for f in files if f.is_file()]
    total_kb = round(sum(f.stat().st_size for f in file_list) / 1024, 1)
    by_source: dict[str, int] = {}
    for f in file_list:
        by_source[f.parent.name] = by_source.get(f.parent.name, 0) + 1
    return {"entries": len(file_list), "total_kb": total_kb, "by_source": by_source,
            "note": "Cache stores compact provenance references only (query, sanitized URL, status) — never secrets.",
            "checked_at": utcnow()}


@router.post("/cache/clear")
def cache_clear():
    removed = 0
    if CACHE_DIR.exists():
        for child in CACHE_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
            elif child.is_file():
                child.unlink(missing_ok=True)
                removed += 1
    return {"cleared": True, "removed": removed, "checked_at": utcnow()}
