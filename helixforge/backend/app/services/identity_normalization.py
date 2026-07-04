"""Identity normalization and cross-source mapping.

Normalizes target / disease / molecule / trial identifiers to a canonical form so
records from different sources can be linked. Lightweight and honest: where a
cross-reference (UniProt, PubChem CID, MeSH/MONDO) is not independently resolved
it is labeled ASSUMPTION/unknown rather than fabricated. RDKit provides canonical
SMILES + InChIKey when available.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.storage import db

try:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover
    RDKIT = False


def normalize_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": "target",
        "gene_symbol": target.get("pref_name") or target.get("target_symbol"),
        "protein_name": target.get("pref_name"),
        "chembl_target_id": target.get("target_chembl_id"),
        "uniprot_accession": target.get("uniprot_accession"),  # only if already present
        "uniprot_status": "KNOWN" if target.get("uniprot_accession") else "NOT_RESOLVED",
        "organism": target.get("organism"),
        "target_type": target.get("target_type"),
        "synonyms": target.get("synonyms") or [],
        "source_type": (SourceType.REAL_TOOL_OUTPUT.value if target.get("target_chembl_id")
                        else SourceType.ASSUMPTION.value),
    }


def normalize_disease(condition: str) -> dict[str, Any]:
    cond = (condition or "").strip()
    return {
        "entity_type": "disease",
        "condition_string": cond,
        "normalized_label": cond.lower() or None,
        "synonyms": [],
        "mesh_id": None, "mondo_id": None, "doid": None,
        "ontology_status": "NOT_RESOLVED",  # no ontology lookup performed — honest
        "source_type": SourceType.ASSUMPTION.value if not cond else SourceType.HEURISTIC_ANALYSIS.value,
    }


def _inchikey(smiles: str) -> Optional[str]:
    if not RDKIT or not smiles:
        return None
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return None


def normalize_molecule(mol: dict[str, Any]) -> dict[str, Any]:
    smi = mol.get("canonical_smiles") or mol.get("smiles")
    canon = None
    if RDKIT and smi:
        m = Chem.MolFromSmiles(smi)
        canon = Chem.MolToSmiles(m) if m is not None else None
    return {
        "entity_type": "molecule",
        "chembl_id": mol.get("molecule_chembl_id"),
        "canonical_smiles": canon or mol.get("canonical_smiles"),
        "inchikey": _inchikey(smi),
        "pubchem_cid": mol.get("pubchem_cid"),  # only if present
        "pubchem_status": "KNOWN" if mol.get("pubchem_cid") else "NOT_RESOLVED",
        "synonyms": mol.get("synonyms") or [],
        "source_type": (SourceType.REAL_TOOL_OUTPUT.value if canon else SourceType.ASSUMPTION.value),
    }


def normalize_trial(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": "clinical_trial",
        "nct_id": ev.get("identifier") if ev.get("identifier_type") == "NCT" else None,
        "condition": ev.get("claim") or ev.get("title"),
        "intervention": None, "phase": None, "status": None,
        "source_type": SourceType.REAL_TOOL_OUTPUT.value,
    }


def _detect_duplicate_molecules(norms: list[dict]) -> list[dict]:
    """Group molecules by canonical SMILES and InChIKey."""
    by_key: dict[str, list[str]] = {}
    for n in norms:
        key = n.get("inchikey") or n.get("canonical_smiles")
        if key:
            by_key.setdefault(key, []).append(n.get("chembl_id") or "?")
    return [{"key": k, "members": v} for k, v in by_key.items() if len(v) > 1]


def normalize_run(run_id: str | None = None) -> dict[str, Any]:
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    pid = run.get("project_id") if run else None
    targets = db.list_records("target_candidates", project_id=pid, limit=200) if pid else []
    mols = db.list_records("molecule_candidates", project_id=pid, limit=500) if pid else []
    trials = [e for e in (db.list_records("evidence_items", project_id=pid, limit=1000) if pid else [])
              if e.get("identifier_type") == "NCT" or "clinicaltrials" in (e.get("source_name") or "").lower()]
    tnorm = [normalize_target(t) for t in targets]
    mnorm = [normalize_molecule(m) for m in mols]
    trnorm = [normalize_trial(t) for t in trials]
    dnorm = normalize_disease(run.get("condition", "")) if run else normalize_disease("")
    payload = {
        "id": f"idnorm-{uuid.uuid4().hex[:8]}", "run_id": run.get("id") if run else None,
        "targets": tnorm, "molecules": mnorm, "trials": trnorm, "disease": dnorm,
        "duplicate_molecules": _detect_duplicate_molecules(mnorm),
        "rdkit_available": RDKIT,
        "note": "Cross-source IDs are resolved only where present; unresolved refs are labeled NOT_RESOLVED/ASSUMPTION.",
        "checked_at": utcnow(),
    }
    try:
        db.insert("identity_normalizations", payload)
    except Exception:
        pass
    return payload
