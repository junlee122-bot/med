from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import RUNTIME_EDITABLE, set_runtime_overrides, settings_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_view():
    """Non-secret settings view. Secrets are masked, never returned in full."""
    return {"editable_keys": sorted(RUNTIME_EDITABLE), "values": settings_status()}


@router.post("")
def update_settings(values: dict):
    """Apply runtime-editable overrides. Secret values are stored but never echoed back."""
    forbidden = sorted(set(values) - RUNTIME_EDITABLE)
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail=f"settings are immutable or unknown: {', '.join(forbidden)}",
        )
    try:
        applied = set_runtime_overrides(values)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Never echo secret values back; report only which keys changed.
    return {"applied_keys": sorted(applied.keys()), "values": settings_status()}
