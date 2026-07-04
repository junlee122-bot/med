from __future__ import annotations

from fastapi import APIRouter

from app.config import RUNTIME_EDITABLE, set_runtime_overrides, settings_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_view():
    """Non-secret settings view. Secrets are masked, never returned in full."""
    return {"editable_keys": sorted(RUNTIME_EDITABLE), "values": settings_status()}


@router.post("")
def update_settings(values: dict):
    """Apply runtime-editable overrides. Secret values are stored but never echoed back."""
    applied = set_runtime_overrides(values)
    # Never echo secret values back; report only which keys changed.
    return {"applied_keys": sorted(applied.keys()), "values": settings_status()}
