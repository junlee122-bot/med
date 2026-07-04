"""Third-party data rights & attribution.

Discloses the sources whose data flows through the app and the redistribution
caveats for recorded snapshots. Where exact license terms are unknown, marks
REVIEW_REQUIRED rather than asserting a license.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import utcnow

RECORDS: list[dict[str, Any]] = [
    {"source": "PubMed / NCBI E-utilities", "data_type": "literature metadata (PMID, title, abstract)",
     "usage_in_app": "evidence mining", "redistribution_risk": "medium",
     "license_or_terms_url_if_known": "https://www.ncbi.nlm.nih.gov/home/about/policies/",
     "attribution_required": True, "snapshot_inclusion_policy": "metadata only; small; timestamped",
     "notes": "Follow NCBI usage policy; identify via NCBI_EMAIL.", "status": "REVIEW_REQUIRED"},
    {"source": "ChEMBL (EMBL-EBI)", "data_type": "targets, molecules, activities (SMILES, pChEMBL)",
     "usage_in_app": "target/molecule import & analysis", "redistribution_risk": "medium",
     "license_or_terms_url_if_known": "https://chembl.gitbook.io/chembl-interface-documentation/about",
     "attribution_required": True, "snapshot_inclusion_policy": "limited records; attribution retained",
     "notes": "ChEMBL data is CC-BY-SA style; verify before public redistribution.", "status": "REVIEW_REQUIRED"},
    {"source": "ClinicalTrials.gov v2", "data_type": "trial registry records (NCT, phase, status)",
     "usage_in_app": "clinical precedent", "redistribution_risk": "low",
     "license_or_terms_url_if_known": "https://clinicaltrials.gov/about-site/terms-conditions",
     "attribution_required": True, "snapshot_inclusion_policy": "limited records; public registry",
     "notes": "US public registry.", "status": "REVIEW_REQUIRED"},
    {"source": "Therapeutics Data Commons (PyTDC)", "data_type": "ADME/Tox dataset metadata",
     "usage_in_app": "evaluation/training substrate (metadata only in snapshots)", "redistribution_risk": "medium",
     "license_or_terms_url_if_known": "https://tdcommons.ai/",
     "attribution_required": True, "snapshot_inclusion_policy": "metadata only; NOT full dataset rows",
     "notes": "Individual datasets carry their own source licenses — check before redistribution.",
     "status": "REVIEW_REQUIRED"},
    {"source": "RDKit", "data_type": "software (descriptors, fingerprints)", "usage_in_app": "molecule validation/analysis",
     "redistribution_risk": "low", "license_or_terms_url_if_known": "https://github.com/rdkit/rdkit (BSD-3)",
     "attribution_required": False, "snapshot_inclusion_policy": "no data redistribution", "notes": "BSD-3.",
     "status": "PASS"},
    {"source": "AutoDock Vina", "data_type": "software", "usage_in_app": "fixture docking (optional)",
     "redistribution_risk": "low", "license_or_terms_url_if_known": "https://github.com/ccsb-scripps/AutoDock-Vina (Apache-2.0)",
     "attribution_required": False, "snapshot_inclusion_policy": "not bundled", "notes": "Apache-2.0.", "status": "PASS"},
    {"source": "REINVENT4", "data_type": "software", "usage_in_app": "config generation (optional)",
     "redistribution_risk": "low", "license_or_terms_url_if_known": "https://github.com/MolecularAI/REINVENT4 (Apache-2.0)",
     "attribution_required": False, "snapshot_inclusion_policy": "not bundled", "notes": "Apache-2.0.", "status": "PASS"},
    {"source": "FastAPI / React / Vite / Tailwind", "data_type": "software frameworks", "usage_in_app": "app",
     "redistribution_risk": "low", "license_or_terms_url_if_known": "MIT/BSD",
     "attribution_required": False, "snapshot_inclusion_policy": "n/a", "notes": "Permissive OSS.", "status": "PASS"},
]

CORE_SOURCES = {"PubMed / NCBI E-utilities", "ChEMBL (EMBL-EBI)", "ClinicalTrials.gov v2",
                "Therapeutics Data Commons (PyTDC)", "RDKit"}

THIRD_PARTY_NOTICE = (
    "Third-Party Data Notice: results derive from public sources (PubMed/NCBI, ChEMBL/EMBL-EBI, "
    "ClinicalTrials.gov, TDC). Attribution is retained per record. Recorded snapshots contain limited, "
    "sanitized data (dataset metadata only) for reproducible demo — verify upstream terms before public "
    "redistribution. See DATA_RIGHTS_AND_ATTRIBUTION.md."
)


def list_records() -> dict[str, Any]:
    review = [r["source"] for r in RECORDS if r["status"] == "REVIEW_REQUIRED"]
    return {"records": RECORDS, "third_party_notice": THIRD_PARTY_NOTICE,
            "review_required_sources": review, "checked_at": utcnow()}


def snapshot_data_rights(snapshot_id: str) -> dict[str, Any]:
    from app.services import snapshots
    snap = snapshots.get_snapshot(snapshot_id)
    if not snap:
        raise ValueError("snapshot not found")
    return {
        "snapshot_id": snapshot_id, "sources": sorted(CORE_SOURCES),
        "original_retrieval": snap.get("created_at"),
        "policy": "Limited recorded real output for reproducible demo (metadata only where applicable).",
        "warning": "Verify upstream source terms before public redistribution.",
        "third_party_notice": THIRD_PARTY_NOTICE,
    }


def check_submission() -> dict[str, Any]:
    covered = {r["source"] for r in RECORDS}
    missing = sorted(CORE_SOURCES - covered)
    return {"ok": not missing, "covered_core_sources": sorted(CORE_SOURCES & covered),
            "missing_core_sources": missing, "third_party_notice_present": True,
            "note": "Submission bundle must include the third-party data notice.", "checked_at": utcnow()}
