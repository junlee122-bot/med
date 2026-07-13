"""Phase 5 — identity, expert review board, professional release, red-team 2.0."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    expert_review_board as erb,
    identity_normalization as idn,
    professional_release as prel,
    red_team_pro as rtp,
)
from app.storage import db

client = TestClient(app)


# ---- Identity normalization ----
@pytest.mark.unit
def test_target_identity_maps_chembl_id():
    n = idn.normalize_target({"target_chembl_id": "CHEMBL203", "pref_name": "EGFR", "organism": "Homo sapiens"})
    assert n["chembl_target_id"] == "CHEMBL203"
    assert n["source_type"] == "REAL_TOOL_OUTPUT"


@pytest.mark.unit
@pytest.mark.local_tool
def test_molecule_identity_inchikey_from_rdkit():
    n = idn.normalize_molecule({"canonical_smiles": "CCO", "molecule_chembl_id": "M1"})
    if idn.RDKIT:
        assert n["inchikey"] and len(n["inchikey"]) >= 14


@pytest.mark.unit
@pytest.mark.local_tool
def test_duplicate_molecule_identity_detected():
    if not idn.RDKIT:
        pytest.skip("RDKit unavailable")
    norms = [idn.normalize_molecule({"canonical_smiles": "CCO", "molecule_chembl_id": "A"}),
             idn.normalize_molecule({"canonical_smiles": "CCO", "molecule_chembl_id": "B"})]
    dups = idn._detect_duplicate_molecules(norms)
    assert len(dups) >= 1


@pytest.mark.unit
def test_identity_unknown_labeled_assumption():
    d = idn.normalize_disease("")
    assert d["ontology_status"] == "NOT_RESOLVED"
    assert d["source_type"] == "ASSUMPTION"


# ---- Expert review board ----
@pytest.mark.integration
def test_expert_review_items_generated_and_by_role():
    res = erb.generate_from_run(None)
    assert "items" in res and "by_role" in res
    # standing safety/clinical/regulatory/report items always exist
    types = {i["item_type"] for i in res["items"]}
    assert {"safety", "clinical_strategy", "regulatory", "report"}.issubset(types)


@pytest.mark.integration
def test_expert_decision_persisted():
    res = erb.generate_from_run(None)
    item = res["items"][0]
    out = erb.record_decision(item["id"], "APPROVE_FOR_PROPOSAL", "Dr X", comment="ok")
    assert out["decision"] == "APPROVE_FOR_PROPOSAL"
    assert out["review_status"] == "REVIEWED"
    assert out["reviewer_role"] == "API_ADMINISTRATOR"
    assert out["signoff_valid"] is False


@pytest.mark.integration
def test_api_administrator_cannot_satisfy_expert_signoff():
    rid = f"errun-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": f"erp-{uuid.uuid4().hex[:6]}",
                                "created_at": "2026-01-02T00:00:00Z", "kind": "agentic"})
    generated = erb.generate_from_run(rid)
    high = [item for item in generated["items"] if item["risk_level"] == "high"]
    for item in high:
        erb.record_decision(item["id"], "APPROVE_FOR_PROPOSAL")
    summary = erb.summary_for_run(rid)
    assert summary["invalid_role_approvals"] == len(high)
    assert summary["signed_off_high_risk"] == 0
    assert summary["all_high_risk_signed_off"] is False
    assert summary["blocks_final_ready"] is True


@pytest.mark.integration
def test_expert_review_pending_blocks_final_ready():
    rid = f"errun-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": f"erp-{uuid.uuid4().hex[:6]}", "created_at": "2026-01-02T00:00:00Z", "kind": "agentic"})
    erb.generate_from_run(rid)
    s = erb.summary_for_run(rid)
    # high-risk items are pending → must block final ready
    assert s["pending_high_risk"] >= 1
    assert s["blocks_final_ready"] is True


@pytest.mark.integration
def test_non_proposal_decisions_do_not_satisfy_high_risk_signoff():
    rid = f"errun-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": f"erp-{uuid.uuid4().hex[:6]}",
                                "created_at": "2026-01-02T00:00:00Z", "kind": "agentic"})
    generated = erb.generate_from_run(rid)
    high = [item for item in generated["items"] if item["risk_level"] == "high"]
    for item in high:
        erb.record_decision(item["id"], "NEEDS_MORE_EVIDENCE")
    summary = erb.summary_for_run(rid)
    assert summary["pending_high_risk"] == 0
    assert summary["unresolved_high_risk"] == len(high)
    assert summary["all_high_risk_signed_off"] is False
    assert summary["blocks_final_ready"] is True


@pytest.mark.integration
def test_expert_review_summary_export_endpoint():
    r = client.post("/api/expert-review/generate-from-run")
    assert r.status_code == 200
    assert client.get("/api/expert-review/items").status_code == 200


# ---- Professional release scorecard ----
@pytest.mark.integration
def test_professional_readiness_computes_categories():
    card = prel.compute()
    assert len(card["categories"]) == 16
    keys = {c["key"] for c in card["categories"]}
    assert {"A", "L", "O", "P"}.issubset(keys)


@pytest.mark.integration
def test_professional_readiness_has_status_and_disclaimer():
    card = prel.compute()
    assert card["status"] in ("NOT_READY", "TECHNICAL_DEMO_READY", "PROPOSAL_READY",
                              "EXPERT_REVIEW_READY", "FINAL_DEMO_READY", "SUBMISSION_READY")
    assert "no wet-lab" in card["disclaimer"].lower()


@pytest.mark.integration
def test_professional_readiness_reflects_expert_review():
    # governance/expert categories are present and scored
    card = prel.compute()
    o = next(c for c in card["categories"] if c["key"] == "O")
    assert o["label"].lower().startswith("expert")


# ---- Professional red-team 2.0 ----
@pytest.mark.integration
def test_professional_red_team_all_scenarios_registered():
    res = rtp.run_suite()
    assert res["total"] >= 20


@pytest.mark.integration
def test_professional_red_team_all_defended():
    res = rtp.run_suite()
    failed = [r for r in res["results"] if not r["defended"]]
    assert res["status"] == "PASS", f"undefended: {[(f['id'], f['name'], f.get('error')) for f in failed]}"


@pytest.mark.integration
def test_red_team_covers_scientific_categories():
    res = rtp.run_suite()
    cats = set(res["by_category"].keys())
    assert {"evidence", "chemistry", "ml", "docking", "clinical", "safety", "governance"}.issubset(cats)


@pytest.mark.integration
def test_professional_ops_endpoints():
    assert client.get("/api/release-readiness/professional/latest").status_code == 200
    assert client.post("/api/red-team/professional/run").status_code == 200
    assert client.post("/api/identity/normalize-run").status_code == 200
