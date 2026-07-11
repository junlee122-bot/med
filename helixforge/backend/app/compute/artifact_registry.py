"""Compute artifact registry + validation.

Validates returned artifacts (allowed type, media, size, checksum, safe filename)
before any artifact may enter candidate ranking. An artifact that fails validation
is labeled GPU_ARTIFACT_UNVERIFIED and cannot be recommended as validated.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from app.compute import schemas as S
from app.compute.security import is_safe_relative_path
from app.models.schemas import SourceType, utcnow
from app.storage import db


def _checksum(content: Any) -> str:
    import json
    if isinstance(content, (dict, list)):
        raw = json.dumps(content, sort_keys=True, default=str).encode()
    elif isinstance(content, str):
        raw = content.encode()
    elif isinstance(content, bytes):
        raw = content
    else:
        raw = str(content).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_artifact(art: dict[str, Any]) -> dict[str, Any]:
    """Return {valid, status, reasons}. Checks type/media/size/filename/checksum."""
    reasons: list[str] = []
    atype = art.get("artifact_type")
    if atype not in S.ALLOWED_ARTIFACT_TYPES:
        reasons.append(f"artifact_type '{atype}' not allowed")
    media = art.get("media_type")
    if media and media not in S.ALLOWED_ARTIFACT_MEDIA:
        reasons.append(f"media_type '{media}' not allowed")
    fname = art.get("filename", "")
    if fname and not is_safe_relative_path(fname):
        reasons.append(f"unsafe filename '{fname}' (path traversal / absolute)")
    size = int(art.get("size_bytes", 0) or 0)
    if size > S.MAX_OUTPUT_SIZE_MB * 1024 * 1024:
        reasons.append("artifact exceeds max size")
    # Checksum: if content present, recompute and compare to declared checksum.
    declared = art.get("declared_checksum") or art.get("checksum_sha256")
    if "content" in art and declared:
        actual = _checksum(art["content"])
        if actual != declared and art.get("checksum_sha256") not in (actual, None):
            # only a mismatch when a declared value exists and differs from recomputed
            if art.get("declared_checksum") and art["declared_checksum"] != actual:
                reasons.append("checksum mismatch")
    status = "VERIFIED" if not reasons else "GPU_ARTIFACT_UNVERIFIED"
    return {"valid": not reasons, "status": status, "reasons": reasons}


def register_artifact(compute_job_id: str, art: dict[str, Any],
                      source_type: str = SourceType.RECORDED_GPU_OUTPUT.value) -> dict[str, Any]:
    """Validate + persist an artifact. Unverified artifacts are stored but flagged."""
    v = validate_artifact(art)
    checksum = art.get("checksum_sha256")
    if not checksum and "content" in art:
        checksum = _checksum(art["content"])
    rec = {
        "id": f"cart-{uuid.uuid4().hex[:10]}", "compute_job_id": compute_job_id,
        "artifact_type": art.get("artifact_type"), "filename": art.get("filename"),
        "media_type": art.get("media_type"), "size_bytes": art.get("size_bytes"),
        "checksum_sha256": checksum,
        "metadata": {k: v for k, v in art.get("metadata", {}).items()} if art.get("metadata") else {},
        "validation_status": v["status"], "validation_reasons": v["reasons"],
        "source_type": source_type if v["valid"] else SourceType.GPU_ARTIFACT_UNVERIFIED.value,
        "created_at": utcnow(),
    }
    db.insert("compute_artifacts", rec)
    return rec


def list_artifacts(compute_job_id: str | None = None) -> list[dict[str, Any]]:
    arts = db.list_records("compute_artifacts", limit=500)
    if compute_job_id:
        arts = [a for a in arts if a.get("compute_job_id") == compute_job_id]
    return arts


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    return db.get("compute_artifacts", artifact_id)
