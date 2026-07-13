from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import (
    activity_normalization, applicability_domain, medchem_review, scientific_language_linter,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["professional-science"])


def _persisted_run_result(table: str, run_id: str, **empty_fields):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    records = db.list_records(table, workflow_run_id=run_id, limit=1)
    if records:
        return records[0]
    return {
        "status": "NOT_COMPUTED", "run_id": run_id, "workflow_run_id": run_id,
        **empty_fields,
    }


# ---- Activity normalization (§4) ----
class NormalizeRequest(BaseModel):
    records: list[dict] = Field(default_factory=list)


@router.post("/activities/normalize")
def activities_normalize(req: NormalizeRequest, run_id: str | None = None):
    if req.records:
        return activity_normalization.normalize_activities(req.records)
    try:
        return activity_normalization.normalize_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/activities/run/{run_id}/summary")
def activities_run_summary(run_id: str):
    return _persisted_run_result(
        "activity_normalizations", run_id,
        normalized=[], endpoint_summaries={}, molecule_reliability={},
        unsupported_units=0, unknown_assay_confidence=0,
    )


@router.get("/activities/molecule/{molecule_id}")
def activities_molecule(molecule_id: str):
    mol = db.get("molecule_candidates", molecule_id)
    if not mol:
        return {"error": "molecule not found", "molecule_id": molecule_id}
    recs = activity_normalization._molecule_activity_records(mol)
    return {"molecule_id": molecule_id, "reliability": activity_normalization.molecule_activity_reliability(recs),
            "normalized": [activity_normalization.normalize_record(r) for r in recs]}


@router.post("/activities/recompute-candidate-scores")
def activities_recompute(run_id: str | None = None, persist: bool = False):
    try:
        return activity_normalization.recompute_candidate_scores(run_id, persist=persist)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- MedChem review (§5) ----
class MedChemMoleculeRequest(BaseModel):
    smiles: str
    label: str | None = None


@router.post("/medchem/review-molecule")
def medchem_review_molecule(req: MedChemMoleculeRequest):
    return medchem_review.review_molecule(req.smiles, req.label)


@router.post("/medchem/review-run")
def medchem_review_run(run_id: str | None = None):
    try:
        return medchem_review.review_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/medchem/run/{run_id}")
def medchem_run(run_id: str):
    return _persisted_run_result(
        "medchem_reviews", run_id, reviews=[], count=0, status_distribution={},
    )


@router.get("/medchem/molecule/{molecule_id}")
def medchem_molecule(molecule_id: str):
    mol = db.get("molecule_candidates", molecule_id)
    if not mol:
        return {"error": "molecule not found"}
    r = medchem_review.review_molecule(mol.get("canonical_smiles") or mol.get("smiles"),
                                       mol.get("label") or mol.get("molecule_chembl_id"))
    r["molecule_id"] = molecule_id
    return r


# ---- Applicability domain (§6) ----
class ApplicabilityRequest(BaseModel):
    smiles: str
    reference_smiles: list[str] = Field(default_factory=list)


@router.post("/applicability/assess-molecule")
def applicability_assess_molecule(req: ApplicabilityRequest):
    return applicability_domain.assess_molecule(req.smiles, req.reference_smiles)


@router.post("/applicability/run")
def applicability_run(run_id: str | None = None):
    try:
        return applicability_domain.assess_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/applicability/run/{run_id}")
def applicability_run_get(run_id: str):
    return _persisted_run_result(
        "applicability_results", run_id, results=[], count=0, status_distribution={},
    )


@router.get("/applicability/molecule/{molecule_id}")
def applicability_molecule(molecule_id: str):
    mol = db.get("molecule_candidates", molecule_id)
    if not mol:
        return {"error": "molecule not found"}
    pid = mol.get("project_id")
    rid = mol.get("workflow_run_id") or mol.get("run_id")
    others = [m.get("canonical_smiles") or m.get("smiles")
              for m in db.list_records("molecule_candidates", project_id=pid,
                                       workflow_run_id=rid, limit=500)
              if m.get("id") != molecule_id]
    return applicability_domain.assess_molecule(mol.get("canonical_smiles") or mol.get("smiles"),
                                                [s for s in others if s], reference_source="run candidate set")


# ---- Scientific language lint (§21) ----
class LanguageLintRequest(BaseModel):
    text: str


@router.post("/language-lint/check")
def language_lint_check(req: LanguageLintRequest):
    return scientific_language_linter.check(req.text)


@router.post("/language-lint/rewrite-safe")
def language_lint_rewrite(req: LanguageLintRequest):
    return scientific_language_linter.rewrite_safe(req.text)
