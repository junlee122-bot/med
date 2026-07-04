from __future__ import annotations

from fastapi import APIRouter

from app.adapters import registry as reg
from app.models.schemas import (
    ClinicalTrialsRequest,
    ClinicalTrialsResponse,
    PubMedResponse,
    PubMedSearchRequest,
)

router = APIRouter(prefix="/api", tags=["literature"])


@router.post("/pubmed/search", response_model=PubMedResponse)
def pubmed_search(req: PubMedSearchRequest):
    out = reg.pubmed.execute(req.model_dump(), project_id=req.project_id)
    return PubMedResponse(**out)


@router.post("/clinicaltrials/search", response_model=ClinicalTrialsResponse)
def clinicaltrials_search(req: ClinicalTrialsRequest):
    out = reg.clinicaltrials.execute(req.model_dump(), project_id=req.project_id)
    return ClinicalTrialsResponse(**out)
