"""Applicability domain and uncertainty engine.

Answers "is this molecule inside the region of chemical space our reference data
covers?" using RDKit Morgan-fingerprint Tanimoto similarity to a reference set.
Without a reference set the status is UNKNOWN (never assumed IN_DOMAIN). Out-of-
domain molecules lower downstream confidence — a model/score cannot be trusted
outside the domain it was derived from.
"""
from __future__ import annotations

import statistics
import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.storage import db

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem
    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover
    RDKIT = False

_OUT_OF_DOMAIN = 0.2   # nearest-neighbour Tanimoto below this ⇒ out of domain
_BORDERLINE = 0.35
_DUPLICATE = 0.99


def _fp(smiles: str):
    m = Chem.MolFromSmiles(smiles) if smiles else None
    if m is None:
        return None, None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=1024), Chem.MolToSmiles(m)


def assess_molecule(smiles: str, reference_smiles: list[str], k: int = 5,
                    reference_source: str = "unknown") -> dict[str, Any]:
    if not RDKIT:
        return {"entity_type": "molecule", "method": "morgan_tanimoto",
                "domain_status": "UNKNOWN", "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "warnings": ["RDKit unavailable"], "confidence_adjustment": -0.2}
    query_fp, canon = _fp(smiles)
    if query_fp is None:
        return {"entity_type": "molecule", "domain_status": "UNKNOWN",
                "warnings": ["invalid query SMILES"], "confidence_adjustment": -0.3,
                "source_type": SourceType.REAL_TOOL_OUTPUT.value}
    # Compare against every provided reference. Self-exclusion (leave-one-out) is
    # the caller's responsibility (assess_run drops the molecule's own record by
    # index) so that a genuine duplicate present in the set is still detectable.
    ref_fps = []
    for rs in reference_smiles:
        fp, _ = _fp(rs)
        if fp is not None:
            ref_fps.append(fp)
    if not ref_fps:
        return {"entity_type": "molecule", "reference_set_source": reference_source,
                "domain_status": "UNKNOWN", "nearest_neighbor_similarity": None,
                "mean_similarity_top_k": None,
                "warnings": ["no usable reference set — applicability domain unknown"],
                "confidence_adjustment": -0.15, "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "created_at": utcnow()}
    sims = sorted(DataStructs.BulkTanimotoSimilarity(query_fp, ref_fps), reverse=True)
    nn = round(sims[0], 3)
    mean_topk = round(statistics.mean(sims[:k]), 3)
    warnings: list[str] = []
    if nn >= _DUPLICATE:
        status = "IN_DOMAIN"
        warnings.append("near-duplicate of reference set — low novelty")
    elif nn < _OUT_OF_DOMAIN:
        status = "OUT_OF_DOMAIN"
        warnings.append("nearest-neighbour similarity very low — predictions unreliable")
    elif nn < _BORDERLINE:
        status = "BORDERLINE"
        warnings.append("borderline domain — treat model/score with caution")
    else:
        status = "IN_DOMAIN"
    adj = {"IN_DOMAIN": 0.0, "BORDERLINE": -0.1, "OUT_OF_DOMAIN": -0.25, "UNKNOWN": -0.15}[status]
    if nn >= _DUPLICATE:
        adj -= 0.05  # novelty penalty
    return {
        "entity_type": "molecule", "method": "morgan_tanimoto_1024b_r2",
        "reference_set_source": reference_source, "reference_size": len(ref_fps),
        "nearest_neighbor_similarity": nn, "mean_similarity_top_k": mean_topk,
        "distance_to_training_domain": round(1.0 - nn, 3), "domain_status": status,
        "is_near_duplicate": nn >= _DUPLICATE, "confidence_adjustment": round(adj, 3),
        "warnings": warnings, "source_type": SourceType.REAL_TOOL_OUTPUT.value, "created_at": utcnow(),
    }


def assess_run(run_id: str | None = None) -> dict[str, Any]:
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    pid = run.get("project_id") if run else None
    rid = run.get("id") if run else None
    mols = (db.list_records("molecule_candidates", project_id=pid, workflow_run_id=rid, limit=500)
            if pid and rid else [])
    indexed = [(m, m.get("canonical_smiles") or m.get("smiles")) for m in mols]
    smiles_all = [s for _, s in indexed if s]
    # Reference set = the run's own ChEMBL-derived candidate set (index-based
    # leave-one-out: drop only THIS molecule's own record, keep true duplicates).
    reference_source = "ChEMBL candidate set (this run)" if smiles_all else "none"
    results = []
    for i, (m, smi) in enumerate(indexed):
        reference = [s for j, (_, s) in enumerate(indexed) if j != i and s]
        r = assess_molecule(smi, reference, reference_source=reference_source)
        r["molecule_id"] = m.get("id")
        r["label"] = m.get("label") or m.get("molecule_chembl_id")
        results.append(r)
    dist: dict[str, int] = {}
    for r in results:
        dist[r["domain_status"]] = dist.get(r["domain_status"], 0) + 1
    payload = {"id": f"appdom-{uuid.uuid4().hex[:8]}", "project_id": pid,
               "run_id": rid, "workflow_run_id": rid,
               "results": results, "count": len(results), "status_distribution": dist,
               "reference_set_source": reference_source, "rdkit_available": RDKIT,
               "disclaimer": "Applicability domain bounds where model/score confidence is meaningful.",
               "checked_at": utcnow(), "created_at": utcnow()}
    try:
        db.insert("applicability_results", payload)
    except Exception:
        pass
    return payload
