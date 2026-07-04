from __future__ import annotations

from fastapi import APIRouter

from app.adapters import registry as reg
from app.models.schemas import RDKitResponse, RDKitSimilarityRequest, RDKitSmilesRequest

router = APIRouter(prefix="/api/rdkit", tags=["rdkit"])


@router.post("/validate", response_model=RDKitResponse)
def validate(req: RDKitSmilesRequest):
    out = reg.rdkit.execute({"operation": "validate", **req.model_dump()}, project_id=req.project_id)
    return RDKitResponse(**out)


@router.post("/descriptors", response_model=RDKitResponse)
def descriptors(req: RDKitSmilesRequest):
    out = reg.rdkit.execute({"operation": "descriptors", **req.model_dump()}, project_id=req.project_id)
    return RDKitResponse(**out)


@router.post("/similarity", response_model=RDKitResponse)
def similarity(req: RDKitSimilarityRequest):
    out = reg.rdkit.execute({"operation": "similarity", **req.model_dump()}, project_id=req.project_id)
    return RDKitResponse(**out)
