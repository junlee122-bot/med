from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.adapters import registry as reg
from app.services import chembl_analysis, molecule_diversity
from app.storage import db

router = APIRouter(prefix="/api", tags=["analysis"])


class DiversityRequest(BaseModel):
    smiles: list[str] | None = None
    project_id: str | None = None
    run_id: str | None = None
    near_dup_threshold: float = 0.85


def _molecules_for(project_id: str | None, run_id: str | None) -> list[dict]:
    if run_id:
        run = db.get("workflow_runs", run_id)
        project_id = project_id or (run.get("project_id") if run else None)
    mols = db.list_records("molecule_candidates", project_id=project_id, limit=500)
    return mols


@router.get("/chembl/assay-summary")
def assay_summary(target_chembl_id: str = Query(default="CHEMBL203"), max_results: int = 50):
    acts = reg.chembl.execute({"operation": "activities", "target_chembl_id": target_chembl_id,
                               "activity_type": "IC50", "max_results": max_results})
    summary = chembl_analysis.assay_quality_summary(target_chembl_id, acts.get("items", []))
    summary["adapter_source_type"] = acts.get("source_type")
    return summary


@router.post("/molecules/analyze-diversity")
def analyze_diversity(req: DiversityRequest):
    smiles = req.smiles
    if not smiles:
        mols = _molecules_for(req.project_id, req.run_id)
        smiles = [m.get("smiles") for m in mols if m.get("smiles")]
    if not smiles:
        raise HTTPException(status_code=400, detail="no SMILES provided or found for project/run")
    return molecule_diversity.analyze_diversity(smiles, req.near_dup_threshold)


@router.get("/molecules/scaffolds")
def scaffolds(run_id: str | None = None, project_id: str | None = None):
    mols = _molecules_for(project_id, run_id)
    smiles = [m.get("smiles") for m in mols if m.get("smiles") and m.get("valid")]
    res = molecule_diversity.analyze_diversity(smiles) if smiles else {"available": False, "scaffolds": []}
    return {"scaffold_count": res.get("scaffold_count", 0), "scaffolds": res.get("scaffolds", []),
            "source_type": res.get("source_type"), "available": res.get("available", False)}


@router.get("/molecules/activity-summary")
def activity_summary(run_id: str | None = None, project_id: str | None = None):
    mols = _molecules_for(project_id, run_id)
    type_counts: dict[str, int] = {}
    pchembl_vals = []
    for m in mols:
        t = m.get("activity_type") or "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
        pv = m.get("pchembl_value")
        if pv not in (None, ""):
            try:
                pchembl_vals.append(float(pv))
            except (TypeError, ValueError):
                pass
    hist: dict[str, int] = {}
    for v in pchembl_vals:
        b = f"{int(v)}-{int(v)+1}"
        hist[b] = hist.get(b, 0) + 1
    return {"molecule_count": len(mols), "standard_type_counts": type_counts,
            "pchembl_available": len(pchembl_vals), "pchembl_histogram": hist,
            "source_type": "REAL_TOOL_OUTPUT" if mols else "TOOL_ERROR"}


@router.post("/molecules/recompute-scores")
def recompute_scores(run_id: str | None = None, project_id: str | None = None):
    """Re-run composite scoring over stored molecules with a duplicate-cluster
    penalty derived from live diversity analysis."""
    from app.services import scoring
    mols = _molecules_for(project_id, run_id)
    valid_smiles = [m.get("smiles") for m in mols if m.get("smiles") and m.get("valid")]
    div = molecule_diversity.analyze_diversity(valid_smiles) if valid_smiles else {"duplicates": [], "near_duplicates": []}
    dup_smiles = set()
    for d in div.get("duplicates", []):
        dup_smiles.add(d.get("canonical_smiles"))
    updated = 0
    for m in mols:
        if not m.get("valid"):
            continue
        inp = scoring.molecule_inputs_from_rdkit(
            {"valid": True, "descriptors": m.get("descriptors")},
            {"pchembl_value": m.get("pchembl_value")} if m.get("pchembl_value") else None,
            m.get("safety_status", "PASS"), tdc_ready=True, provenance=0.7)
        # Diversity penalty: duplicate/near-duplicate cluster lowers novelty proxy.
        is_dup = any(nd.get("a") is not None for nd in div.get("near_duplicates", []))
        if is_dup:
            inp["novelty_or_diversity_proxy"] = 0.25
        sc = scoring.score_molecule(inp)
        m["composite_score"] = sc["score"]
        m["recommendation"] = sc["recommendation"]
        m["score_breakdown"] = sc["breakdown"]
        db.insert("molecule_candidates", m)
        updated += 1
    return {"updated": updated, "duplicate_clusters": len(div.get("duplicates", [])),
            "near_duplicate_pairs": len(div.get("near_duplicates", [])),
            "diversity_score": div.get("diversity_score")}
