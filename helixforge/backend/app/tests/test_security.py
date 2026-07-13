"""Security / privacy tests."""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.adapters.base import ToolAdapter
from app.adapters.vina_adapter import VinaAdapter
from app.main import app
from app.api.health import _network_probe
from app.models.schemas import SourceType, ValidationStatus
from app.services import audit
from app.services.provenance import redact_secrets
from app.storage import db

client = TestClient(app)


@pytest.mark.unit
def test_redact_secrets_removes_key_params():
    out = redact_secrets("https://eutils.ncbi.nlm.nih.gov/x?api_key=SUPERSECRET123&db=pubmed")
    assert "SUPERSECRET123" not in out
    assert "REDACTED" in out


@pytest.mark.unit
def test_redact_secrets_handles_token_and_key_variants():
    for param in ("token", "apikey", "key"):
        out = redact_secrets(f"http://x?{param}=abcdef123456")
        assert "abcdef123456" not in out


@pytest.mark.unit
def test_redact_secrets_recurses_through_export_payloads():
    secret = "sk-ant-example-secret-123456"
    out = redact_secrets({"rows": [{"api_key": secret, "message": secret}]})
    assert secret not in str(out)
    assert out["rows"][0]["api_key"] == "***REDACTED***"


@pytest.mark.unit
def test_redact_secrets_preserves_token_metrics_and_presence_flags():
    out = redact_secrets({"tokens_in": 120, "max_output_tokens": 500,
                          "configured": {"ncbi_api_key": True}})
    assert out["tokens_in"] == 120
    assert out["max_output_tokens"] == 500
    assert out["configured"]["ncbi_api_key"] is True


@pytest.mark.integration
def test_audit_persistence_recursively_redacts_observable_fields():
    secret = "sk-ant-audit-secret-123456"
    run_id = f"audit-redaction-{uuid.uuid4().hex}"
    event_id = audit.record_tool_run(
        tool_name="SecretProbe",
        tool_category="test",
        source_type=SourceType.TOOL_ERROR,
        input_summary=f"token={secret}",
        output_summary=f"authorization={secret}",
        validation_status=ValidationStatus.FAILED,
        project_id="project-redaction",
        workflow_run_id=run_id,
        errors=[{"nested": {"api_key": secret}}],
        warnings=[f"authorization={secret}"],
    )
    event = db.get("audit_events", event_id)
    tool_runs = db.list_records("tool_runs", workflow_run_id=run_id)
    assert event is not None
    assert len(tool_runs) == 1
    assert secret not in str(event)
    assert secret not in str(tool_runs[0])
    assert event["workflow_run_id"] == run_id
    assert tool_runs[0]["project_id"] == "project-redaction"


@pytest.mark.integration
def test_base_adapter_redacts_payload_and_exception_before_audit():
    secret = "sk-ant-adapter-secret-123456"
    run_id = f"adapter-redaction-{uuid.uuid4().hex}"

    class SecretAdapter(ToolAdapter):
        id = "secret-probe"
        name = "Secret Probe"
        category = "test"

        def health_check(self):
            raise RuntimeError(f"token={secret}")

        def run(self, _payload):
            raise RuntimeError(f"api_key={secret}")

    adapter = SecretAdapter()
    health = adapter.health()
    result = adapter.execute(
        {"api_key": secret, "query": "safe"},
        project_id="project-redaction",
        workflow_run_id=run_id,
    )
    persisted = db.list_records("tool_runs", workflow_run_id=run_id)
    assert len(persisted) == 1
    assert secret not in health.detail
    assert secret not in str(result)
    assert secret not in str(persisted[0])


@pytest.mark.integration
def test_security_audit_endpoint():
    r = client.get("/api/security/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("PASS", "WARN", "FAIL")
    assert any(f["category"] == "env_ignored" for f in body["findings"])
    # No full secret is ever returned.
    assert "secret_masked_example" in body


@pytest.mark.integration
def test_cache_stats_endpoint():
    r = client.get("/api/cache/stats")
    assert r.status_code == 200
    assert "entries" in r.json()


@pytest.mark.unit
def test_network_health_timeout_does_not_wait_for_worker_shutdown():
    class SlowAdapter:
        id = "slow"
        name = "Slow"
        category = "test"

        @staticmethod
        def health():
            time.sleep(0.25)

    started = time.monotonic()
    result = _network_probe(SlowAdapter(), 0.02, "live")
    elapsed = time.monotonic() - started
    assert result["last_error"] == "timeout"
    # Leave headroom for busy CI hosts while still proving we did not wait for
    # the adapter's full 250 ms worker sleep.
    assert elapsed < 0.20


@pytest.mark.unit
def test_database_rejects_cross_project_id_overwrite():
    entity_id = f"collision-{uuid.uuid4().hex}"
    db.insert("evidence_items", {"id": entity_id, "project_id": "project-a"})
    with pytest.raises(ValueError, match="Cross-project id collision"):
        db.insert("evidence_items", {"id": entity_id, "project_id": "project-b"})


@pytest.mark.unit
def test_database_rejects_cross_run_id_overwrite():
    entity_id = f"run-collision-{uuid.uuid4().hex}"
    db.insert("evidence_items", {
        "id": entity_id, "project_id": "same-project", "workflow_run_id": "run-a",
    })
    with pytest.raises(ValueError, match="Cross-run id collision"):
        db.insert("evidence_items", {
            "id": entity_id, "project_id": "same-project", "workflow_run_id": "run-b",
        })


@pytest.mark.unit
def test_database_normalizes_unbounded_negative_limit():
    assert db.list_records("evidence_items", limit=-1) == []


@pytest.mark.unit
@pytest.mark.parametrize("field", ["receptor_fixture", "ligand_fixture"])
def test_vina_rejects_fixture_path_escape_before_execution(field):
    result = VinaAdapter().run({field: "../../outside.pdbqt"})
    assert result["status"] == "error"
    assert result["source_type"] == "TOOL_ERROR"
    assert result["scores"] == []
    assert "fixture directory" in " ".join(result["errors"])
