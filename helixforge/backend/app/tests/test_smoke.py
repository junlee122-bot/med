"""Smoke tests for HelixForge AI backend.

Network-dependent tests assert honest behavior: on success the SourceType must be
REAL_TOOL_OUTPUT with parsed fields; if the live API is unreachable the adapter
must return TOOL_ERROR (never fabricated data) and the test skips the strict
content assertions. Local-tool tests (RDKit, config generation, report) run
deterministically offline.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("HELIXFORGE_DATA_DIR", "/tmp/helixforge-test-data")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.schemas import SourceType  # noqa: E402

client = TestClient(app)


def _is_real(body: dict) -> bool:
    return body.get("source_type") == SourceType.REAL_TOOL_OUTPUT.value


# --- health ---------------------------------------------------------------
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tools_health():
    r = client.get("/api/tools/health")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert {"PubMed", "ClinicalTrials.gov", "ChEMBL", "RDKit", "TDC/PyTDC", "AutoDock Vina", "REINVENT4"} <= names


# --- PubMed ---------------------------------------------------------------
def test_pubmed_search():
    r = client.post("/api/pubmed/search", json={"query": "EGFR non-small cell lung cancer resistance", "max_results": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] in (SourceType.REAL_TOOL_OUTPUT.value, SourceType.TOOL_ERROR.value)
    if _is_real(body):
        assert len(body["items"]) >= 1
        assert body["items"][0]["pmid"]
        assert body["items"][0]["title"]


# --- ClinicalTrials.gov ---------------------------------------------------
def test_clinicaltrials_search():
    r = client.post("/api/clinicaltrials/search", json={"condition": "non-small cell lung cancer", "query": "EGFR", "max_results": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] in (SourceType.REAL_TOOL_OUTPUT.value, SourceType.TOOL_ERROR.value)
    if _is_real(body):
        assert len(body["items"]) >= 1
        assert body["items"][0]["nct_id"].startswith("NCT")


# --- ChEMBL ---------------------------------------------------------------
def test_chembl_target_search():
    r = client.post("/api/chembl/search-targets", json={"query": "EGFR", "max_results": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] in (SourceType.REAL_TOOL_OUTPUT.value, SourceType.TOOL_ERROR.value)
    if _is_real(body):
        assert len(body["items"]) >= 1
        assert body["items"][0]["target_chembl_id"].startswith("CHEMBL")


# --- RDKit (real, offline) ------------------------------------------------
def test_rdkit_validate_valid_smiles():
    r = client.post("/api/rdkit/descriptors", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
    assert r.status_code == 200
    body = r.json()
    if body["source_type"] == SourceType.CONFIGURED_BUT_NOT_RUN.value:
        pytest.skip("RDKit not installed in this environment")
    assert body["valid"] is True
    assert body["canonical_smiles"]
    assert body["descriptors"]["mol_weight"] > 0


def test_rdkit_reject_invalid_smiles():
    r = client.post("/api/rdkit/validate", json={"smiles": "CC(C)(C"})
    assert r.status_code == 200
    body = r.json()
    if body["source_type"] == SourceType.CONFIGURED_BUT_NOT_RUN.value:
        pytest.skip("RDKit not installed in this environment")
    assert body["valid"] is False
    assert body["errors"]  # a real parse failure is reported


# --- TDC ------------------------------------------------------------------
def test_tdc_datasets():
    r = client.get("/api/tdc/datasets")
    assert r.status_code == 200
    assert len(r.json()["datasets"]) >= 6


def test_tdc_load_dataset():
    r = client.post("/api/tdc/load", json={"task": "ADME", "dataset": "Caco2_Wang"})
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] in (
        SourceType.REAL_TOOL_OUTPUT.value,
        SourceType.CONFIGURED_BUT_NOT_RUN.value,
        SourceType.TOOL_ERROR.value,
    )
    if _is_real(body):
        assert body["row_count"] > 0
        assert set(body["split_summary"]) == {"train", "valid", "test"}


# --- Vina (health only; binary not required) ------------------------------
def test_vina_health_check():
    r = client.get("/api/tools/health")
    vina = next(t for t in r.json()["tools"] if t["name"] == "AutoDock Vina")
    assert vina["status"] in ("AVAILABLE", "DEGRADED", "NOT_CONFIGURED")


def test_vina_fixture_dock_without_engine_is_honest():
    r = client.post("/api/vina/fixture-dock", json={})
    assert r.status_code == 200
    body = r.json()
    # If Vina is not installed it must NOT fabricate a score.
    assert body["source_type"] in (
        SourceType.REAL_TOOL_OUTPUT.value,
        SourceType.CONFIGURED_BUT_NOT_RUN.value,
        SourceType.TOOL_ERROR.value,
    )
    if body["source_type"] != SourceType.REAL_TOOL_OUTPUT.value:
        assert body["scores"] == []


# --- REINVENT4 config gen (offline) --------------------------------------
def test_reinvent_config_generation():
    r = client.post("/api/reinvent/create-config", json={"target_name": "EGFR", "max_molecules": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["config_path"].endswith(".toml")
    # Not installed → CONFIGURED_BUT_NOT_RUN; installed → could be more. Never fabricated smiles.
    assert body["generated_smiles"] == []
    import os as _os
    assert _os.path.exists(body["config_path"])


# --- Report ---------------------------------------------------------------
def test_report_generation():
    r = client.post("/api/report/generate", json={"project_id": "test-proj", "title": "Smoke Report"})
    assert r.status_code == 200
    body = r.json()
    assert body["report_id"].startswith("rep-")
    assert "research decision support only" in body["markdown"].lower()
    assert "provenance_counts" in body["json_audit"]
