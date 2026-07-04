from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import snapshots
from app.storage import db

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


class CreateSnapshotRequest(BaseModel):
    name: str = "EGFR/NSCLC recorded run"
    description: str = ""
    created_by: str = "user"


@router.get("")
def list_snapshots():
    return {"snapshots": snapshots.list_snapshots()}


@router.post("/create-from-run/{run_id}")
def create_from_run(run_id: str, req: CreateSnapshotRequest):
    try:
        return snapshots.create_snapshot_from_run(run_id, req.name, req.description, req.created_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    snap = snapshots.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return snap


@router.post("/{snapshot_id}/replay")
def replay_snapshot(snapshot_id: str):
    try:
        return snapshots.replay_snapshot(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: str):
    ok = snapshots.delete_snapshot(snapshot_id)
    if not ok:
        raise HTTPException(status_code=400, detail="snapshot not found or is built-in (cannot delete)")
    return {"deleted": snapshot_id}


@router.get("/{snapshot_id}/manifest")
def snapshot_manifest(snapshot_id: str):
    try:
        return snapshots.snapshot_manifest(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{snapshot_id}/export")
def export_snapshot(snapshot_id: str):
    try:
        return snapshots.export_snapshot(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
