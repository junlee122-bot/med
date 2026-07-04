from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import (
    activity_normalization, applicability_domain, medchem_review, scientific_language_linter,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["professional-science"])


# ---- Activity normalization (§4) ----
class NormalizeRequest(BaseModel):
    records: list[dict] = []


@router.post("/activities/normalize")
def activities_normalize(req: NormalizeRequest):
    if req.records:
        return activity_normalization.normalize_activities(req.records)
    return activity_normalization.normalize_run(None)


@router.get("/activities/run/{run_id}/summary")
def activities_run_summary(run_id: str):
    return activity_normalization.normalize_run(run_id)


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
    return activity_normalization.recompute_candidate_scores(run_id, persist=persist)


# ---- MedChem review (§5) ----
class MedChemMoleculeRequest(BaseModel):
    smiles: str
    label: str | None = None


@router.post("/medchem/review-molecule")
def medchem_review_molecule(req: MedChemMoleculeRequest):
    return medchem_review.review_molecule(req.smiles, req.label)


@router.post("/medchem/review-run")
def medchem_review_run(run_id: str | None = None):
    return medchem_review.review_run(run_id)


@router.get("/medchem/run/{run_id}")
def medchem_run(run_id: str):
    return medchem_review.review_run(run_id)


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
    reference_smiles: list[str] = []


@router.post("/applicability/assess-molecule")
def applicability_assess_molecule(req: ApplicabilityRequest):
    return applicability_domain.assess_molecule(req.smiles, req.reference_smiles)


@router.post("/applicability/run")
def applicability_run(run_id: str | None = None):
    return applicability_domain.assess_run(run_id)


@router.get("/applicability/run/{run_id}")
def applicability_run_get(run_id: str):
    return applicability_domain.assess_run(run_id)


@router.get("/applicability/molecule/{molecule_id}")
def applicability_molecule(molecule_id: str):
    mol = db.get("molecule_candidates", molecule_id)
    if not mol:
        return {"error": "molecule not found"}
    pid = mol.get("project_id")
    others = [m.get("canonical_smiles") or m.get("smiles")
              for m in db.list_records("molecule_candidates", project_id=pid, limit=500)
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
