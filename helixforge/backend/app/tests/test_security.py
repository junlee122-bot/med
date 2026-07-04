"""Security / privacy tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.provenance import redact_secrets

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
