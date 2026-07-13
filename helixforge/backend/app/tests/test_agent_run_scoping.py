from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters import registry as reg
from app.adapters.base import ToolAdapter
from app.agents.admet_agent import AdmetAgent
from app.agents.base import AgentContext
from app.agents.cheminformatics_validator_agent import CheminformaticsValidatorAgent
from app.agents.citation_verifier_agent import CitationVerifierAgent
from app.agents.critic_agent import CriticAgent
from app.agents.evidence_miner_agent import EvidenceMinerAgent
from app.agents.safety_auditor_agent import SafetyAuditorAgent
from app.agents.target_scout_agent import TargetScoutAgent
from app.models.schemas import HealthStatus, SourceType, ToolHealth
from app.storage import db


pytestmark = pytest.mark.unit


def _result(**values: Any) -> dict[str, Any]:
    return {
        "source_type": SourceType.REAL_TOOL_OUTPUT.value,
        "errors": [],
        "warnings": [],
        **values,
    }


def _exercise_run(monkeypatch: pytest.MonkeyPatch, project_id: str, run_id: str) -> None:
    monkeypatch.setattr(
        reg,
        "pubmed",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(items=[{
            "pmid": "12345678",
            "title": "EGFR evidence",
            "abstract": "A public-data signal.",
            "year": "2024",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        }])),
    )
    monkeypatch.setattr(
        reg,
        "chembl",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(items=[{
            "target_chembl_id": "CHEMBL203",
            "pref_name": "EGFR",
            "organism": "Homo sapiens",
            "target_type": "SINGLE PROTEIN",
            "confidence_score": 9,
        }])),
    )
    monkeypatch.setattr(
        reg,
        "clinicaltrials",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(items=[])),
    )
    monkeypatch.setattr(
        reg,
        "rdkit",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(
            valid=True,
            canonical_smiles="CCO",
            descriptors={
                "mol_weight": 46.1,
                "logp": -0.3,
                "tpsa": 20.2,
                "qed": 0.5,
                "lipinski_pass": True,
                "lipinski_violations": 0,
            },
        )),
    )
    monkeypatch.setattr(
        reg,
        "safety",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(
            status="PASS", categories=[]
        )),
    )
    monkeypatch.setattr(
        reg,
        "tdc",
        SimpleNamespace(execute=lambda *args, **kwargs: _result(
            dataset_name="Caco2_Wang",
            task="regression",
            row_count=100,
            columns=["Drug", "Y"],
            split_summary={"train": 80, "test": 20},
        )),
    )

    ctx = AgentContext(
        project_id=project_id,
        workflow_run_id=run_id,
        max_results=2,
        injections={
            "contradictory_evidence": True,
            "fake_citation": True,
            "safety_flag": True,
        },
    )

    EvidenceMinerAgent().run(ctx)
    CitationVerifierAgent().run(ctx)
    TargetScoutAgent().run(ctx)
    ctx.shared["molecules_raw"] = [{
        "molecule_chembl_id": "CHEMBL-MOL-1",
        "smiles": "CCO",
        "pchembl_value": 6.5,
        "source": "test",
        "source_type": SourceType.REAL_TOOL_OUTPUT.value,
    }]
    CheminformaticsValidatorAgent().run(ctx)
    AdmetAgent().run(ctx)
    SafetyAuditorAgent().run(ctx)


def test_agent_owned_records_are_run_scoped_and_do_not_collide(monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid.uuid4().hex[:8]
    first_run = f"scope-a-{suffix}"
    second_run = f"scope-b-{suffix}"
    _exercise_run(monkeypatch, f"project-a-{suffix}", first_run)
    _exercise_run(monkeypatch, f"project-b-{suffix}", second_run)

    tables = (
        "evidence_items",
        "target_candidates",
        "molecule_candidates",
        "tdc_dataset_records",
        "safety_flags",
    )
    for table in tables:
        first = db.list_records(table, workflow_run_id=first_run)
        second = db.list_records(table, workflow_run_id=second_run)
        assert first, f"{table} should contain first-run records"
        assert second, f"{table} should contain second-run records"
        assert all(row["workflow_run_id"] == first_run for row in first)
        assert all(row["workflow_run_id"] == second_run for row in second)
        assert {row["id"] for row in first}.isdisjoint({row["id"] for row in second})

    persisted_molecule = db.list_records(
        "molecule_candidates", workflow_run_id=first_run
    )[0]
    assert persisted_molecule["rank"] == 1


def test_critic_accepts_failed_citation_ids() -> None:
    ctx = AgentContext(project_id="critic-project", workflow_run_id="critic-run")
    ctx.shared["fake_citation_flagged"] = ["ev-critic-run-fake-demo"]
    ctx.shared["hypotheses"] = []

    output = CriticAgent().run(ctx)

    assert any(
        check["check"] == "failed_citations_demoted" and check["ok"]
        for check in output.validation_checks
    )


class _OwnershipProbeAdapter(ToolAdapter):
    id = "ownership-probe"
    name = "Ownership Probe"

    def health_check(self) -> ToolHealth:
        return ToolHealth(
            tool_id=self.id,
            name=self.name,
            category="test",
            status=HealthStatus.AVAILABLE,
            mode="test",
            detail="test",
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _result(
            received_project_id=payload.get("project_id"),
            received_workflow_run_id=payload.get("workflow_run_id"),
        )


def test_adapter_execute_threads_authoritative_run_ownership() -> None:
    output = _OwnershipProbeAdapter().execute(
        {"project_id": "spoofed-project", "workflow_run_id": "spoofed-run"},
        project_id="real-project",
        workflow_run_id="real-run",
    )

    assert output["received_project_id"] == "real-project"
    assert output["received_workflow_run_id"] == "real-run"
