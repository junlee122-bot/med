from __future__ import annotations

from fastapi import APIRouter

from app.adapters import registry as reg
from app.models.schemas import ChemblActivitiesRequest, ChemblResponse, ChemblSearchRequest

router = APIRouter(prefix="/api/chembl", tags=["chembl"])


@router.post("/search-targets", response_model=ChemblResponse)
def search_targets(req: ChemblSearchRequest):
    out = reg.chembl.execute({"operation": "targets", **req.model_dump()}, project_id=req.project_id)
    return ChemblResponse(**out)


@router.post("/search-molecules", response_model=ChemblResponse)
def search_molecules(req: ChemblSearchRequest):
    out = reg.chembl.execute({"operation": "molecules", **req.model_dump()}, project_id=req.project_id)
    return ChemblResponse(**out)


@router.post("/activities", response_model=ChemblResponse)
def activities(req: ChemblActivitiesRequest):
    out = reg.chembl.execute({"operation": "activities", **req.model_dump()}, project_id=req.project_id)
    return ChemblResponse(**out)
