"""Phase 4 tests: hygiene, source-type governance, health tiers, KO safety lint."""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import source_type_governance as gov
from app.services.safety_lint import lint_report, rewrite_overclaims_ko, lint_submission_artifact
from app.storage import db

client = TestClient(app)


# ---- Health tiers ----
@pytest.mark.integration
def test_tools_health_local_does_not_call_network():
    t0 = time.time()
    r = client.get("/api/tools/health", params={"mode": "local"})
    elapsed = time.time() - t0
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "local"
    assert body["network_used"] is False
    assert elapsed < 3.0  # no network → fast
    assert len(body["tools"]) == 9


@pytest.mark.integration
def test_tool_registry_response_includes_probe_mode():
    r = client.get("/api/tools/health", params={"mode": "local"})
    tools = r.json()["tools"]
    assert all("probe_mode" in t and "network_used" in t for t in tools)


@pytest.mark.integration
def test_tools_health_live_has_timeout_param():
    r = client.get("/api/tools/health", params={"mode": "live", "timeout_seconds": 5})
    assert r.status_code == 200
    assert r.json()["mode"] == "live"


# ---- Korean safety lint ----
@pytest.mark.unit
def test_korean_safety_lint_blocks_synthesis_route():
    res = lint_report("이 분자의 합성 경로는 다음과 같다. 책임은 연구자에게 있습니다.")
    assert res["status"] == "BLOCKED"
    assert "ko" in res["languages"]


@pytest.mark.unit
def test_korean_safety_lint_blocks_dosage():
    assert lint_report("권장 투여량 지침입니다. 책임은 연구자에게 있습니다.")["status"] == "BLOCKED"
    assert lint_report("반응 조건은 다음과 같다. 책임은 연구자에게 있습니다.")["status"] == "BLOCKED"


@pytest.mark.unit
def test_korean_overclaim_rewrite():
    res = rewrite_overclaims_ko("이 시스템은 신약을 발견했다. 임상 효과가 입증됐다.")
    assert res["changed"]
    assert "신약을 발견했다" not in res["rewritten"]


@pytest.mark.unit
def test_submission_artifacts_pass_multilingual_safety_lint():
    good = "HelixForge 후보 우선순위화 결과. 연구 의사결정 보조 도구이며 책임은 연구자에게 있습니다."
    assert lint_submission_artifact(good)["status"] in ("PASS", "REVIEW_REQUIRED")
    bad = "합성법: 단계별 합성. 책임은 연구자에게 있습니다."
    assert lint_submission_artifact(bad)["status"] == "BLOCKED"


# ---- Source-type governance ----
@pytest.mark.unit
def test_source_type_audit_flags_missing_source_type():
    pid = f"proj-gov-{uuid.uuid4().hex[:6]}"
    db.insert("molecule_candidates", {"id": f"mol-nost-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                      "created_at": "2026-01-01T00:00:00Z", "smiles": "CCO", "valid": True})
    res = gov.audit()
    assert res["status"] in ("REVIEW_REQUIRED", "BLOCKED")
    assert any("mol-nost" in x for x in res["missing_source_type_records"])


@pytest.mark.unit
def test_replay_run_has_recorded_source_type_not_real():
    pid = f"proj-rp-{uuid.uuid4().hex[:6]}"
    rid = f"replay-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z",
                                "kind": "agentic_replay", "replay_mode": True,
                                "source_types": ["REAL_TOOL_OUTPUT"]})
    res = gov.audit()
    assert any(rid in x for x in res["real_vs_replay_conflicts"])
    assert res["status"] == "BLOCKED"


@pytest.mark.unit
def test_configured_not_run_not_overclaimed():
    pid = f"proj-cnr-{uuid.uuid4().hex[:6]}"
    db.insert("reports", {"id": f"rep-bad-{uuid.uuid4().hex[:6]}", "project_id": pid,
                          "created_at": "2026-01-01T00:00:00Z",
                          "markdown": "AutoDock Vina CONFIGURED_BUT_NOT_RUN produced a real result and executed successfully."})
    res = gov.audit()
    assert res["configured_not_run_overclaimed"]
    assert res["status"] == "BLOCKED"


@pytest.mark.integration
def test_source_types_audit_endpoint():
    r = client.get("/api/source-types/audit")
    assert r.status_code == 200
    assert "source_type_counts" in r.json()


# ---- Safe-context awareness (no false block on the app's own safety policy) ----
@pytest.mark.unit
def test_safe_policy_statement_not_blocked_en():
    text = ("No wet-lab protocols, synthesis routes, reagents, reaction conditions, "
            "purification, dosage, or medical advice — by policy. 책임은 연구자에게 있습니다.")
    assert lint_report(text)["status"] != "BLOCKED"


@pytest.mark.unit
def test_safe_policy_statement_not_blocked_ko():
    text = "무합성경로 정책, 합성 경로·의료 자문 미제공. 책임은 연구자에게 있습니다."
    assert lint_report(text)["status"] != "BLOCKED"


@pytest.mark.unit
def test_actionable_synthesis_still_blocked_after_scrub():
    # The scrub must not weaken genuine actionable content detection.
    assert lint_report("다음은 합성 경로입니다: 80도로 가열. 책임은 연구자에게 있습니다.")["status"] == "BLOCKED"
    assert lint_report("Step-by-step synthesis: heat reagents to 80C.", require_disclaimer=False)["status"] == "BLOCKED"


# ---- Full Korean proposal generator ----
@pytest.mark.unit
def test_full_korean_proposal_contains_rubric_sections():
    from app.services import proposal_writer
    md = proposal_writer.build_full_proposal_ko()
    for needle in ("분야 4", "멀티", "안전", "한계", "책임은 연구자", "CONFIGURED_BUT_NOT_RUN"):
        assert needle in md, f"missing section marker: {needle}"


@pytest.mark.unit
def test_proposal_artifacts_are_export_safe():
    from app.services import proposal_writer
    for builder in (proposal_writer.build_full_proposal_ko,
                    proposal_writer.build_peer_one_pager_ko,
                    proposal_writer.build_qa_defense_ko):
        lr = lint_report(builder())
        assert lr["export_safe"] is True
        assert lr["status"] != "BLOCKED"


@pytest.mark.unit
def test_proposal_has_no_forbidden_overclaims():
    from app.services.safety_lint import detect_overclaims
    from app.services import proposal_writer
    assert detect_overclaims(proposal_writer.build_full_proposal_ko()) == []


@pytest.mark.integration
def test_proposal_generate_endpoint_persists_artifact():
    r = client.post("/api/proposal/generate", json={"kind": "full_proposal_ko"})
    assert r.status_code == 200
    body = r.json()
    assert body["export_safe"] is True
    assert body["kind"] == "full_proposal_ko"


# ---- Data rights & attribution ----
@pytest.mark.unit
def test_data_rights_records_exist_for_core_sources():
    from app.services import data_rights
    covered = {r["source"] for r in data_rights.RECORDS}
    assert data_rights.CORE_SOURCES.issubset(covered)


@pytest.mark.unit
def test_data_rights_check_submission_ok():
    from app.services import data_rights
    res = data_rights.check_submission()
    assert res["ok"] is True
    assert res["missing_core_sources"] == []


@pytest.mark.integration
def test_submission_bundle_includes_data_rights_notice():
    from app.services import submission_pack
    bundle = submission_pack.bundle()
    assert "data_rights" in bundle
    assert bundle["third_party_data_notice"]
    assert "records" in bundle["data_rights"]


@pytest.mark.integration
def test_data_rights_endpoint():
    r = client.get("/api/data-rights")
    assert r.status_code == 200
    assert len(r.json()["records"]) >= 5
