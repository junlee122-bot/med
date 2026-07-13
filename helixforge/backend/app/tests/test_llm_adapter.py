"""Phase 7 — LLM adapter: no-key fallback, budget, safety, schema, ledger, router.
All offline (deterministic FakeLLMClient); no live API calls."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.llm import llm_adapter, model_router, prompt_templates
from app.llm.config import get_llm_config
from app.llm.schemas import LLMCallPurpose, LLMMode, ReasoningSourceType
from app.main import app
from app.storage import db
from app.tests.fakes.fake_llm_client import FakeLLMClient

client = TestClient(app)
PLAN_KEYS = ["objective", "selected_stages"]


@pytest.fixture(autouse=True)
def _reset_costs():
    model_router._reset_all_for_tests()
    yield


@pytest.mark.unit
def test_budget_reservation_cannot_be_settled_twice_or_forged():
    reserved = model_router.reserve_budget(0.001, "reservation-run")
    assert reserved["allowed"] is True
    reservation_id = reserved["reservation_id"]
    model_router.settle_reservation(reservation_id, 0.001)
    with pytest.raises(ValueError, match="already-settled"):
        model_router.settle_reservation(reservation_id, 0.001)
    with pytest.raises(ValueError, match="unknown"):
        model_router.settle_reservation("forged-reservation", 0.001)


# ---- No key / deterministic fallback ----
@pytest.mark.unit
def test_llm_no_key_falls_back(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING,
                               prompt_template_id="dynamic_planner", user_prompt="plan EGFR",
                               required_keys=PLAN_KEYS, record_ledger=False)
    assert res.ok is False
    assert res.reasoning_source_type == ReasoningSourceType.DETERMINISTIC_FALLBACK
    assert res.fallback_used is True


@pytest.mark.unit
def test_llm_mocked_valid_call(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan")
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING,
                               prompt_template_id="dynamic_planner", user_prompt="plan EGFR",
                               required_keys=PLAN_KEYS, list_keys=["selected_stages"],
                               client=fake, record_ledger=False)
    assert res.ok is True
    assert res.reasoning_source_type == ReasoningSourceType.REAL_LLM_OUTPUT
    assert res.data and res.data["objective"]
    assert len(fake.calls) == 1


@pytest.mark.unit
def test_llm_invalid_schema_falls_back(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_RETRIES", "1")
    fake = FakeLLMClient(response="plan", invalid_json=True)
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING,
                               prompt_template_id="dynamic_planner", user_prompt="plan",
                               required_keys=PLAN_KEYS, client=fake, record_ledger=False)
    assert res.ok is False
    assert res.reasoning_source_type == ReasoningSourceType.LLM_OUTPUT_INVALID
    # one original + one repair attempt
    assert len(fake.calls) == 2


@pytest.mark.unit
def test_llm_schema_repair_is_safety_screened(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_RETRIES", "1")

    class UnsafeRepairClient:
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            text = "not-json" if self.calls == 1 else (
                '{"objective":"step-by-step synthesis with reagent list",'
                '"selected_stages":[]}'
            )
            return {"text": text, "tokens_in": 20, "tokens_out": 20,
                    "stop_reason": "end_turn", "model": "fake"}

    fake = UnsafeRepairClient()
    res = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner",
        user_prompt="plan",
        required_keys=PLAN_KEYS,
        client=fake,
        record_ledger=False,
    )
    assert fake.calls == 2
    assert res.reasoning_source_type == ReasoningSourceType.LLM_SAFETY_BLOCKED
    assert res.safety_status == "SAFETY_BLOCKED"


@pytest.mark.unit
def test_llm_budget_blocked(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_COST_PER_RUN_USD", "0.0000001")
    fake = FakeLLMClient(response="plan")
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.HYPOTHESIS_REASONING,
                               prompt_template_id="hypothesis_reasoner", user_prompt="x" * 5000,
                               required_keys=["hypotheses"], run_id="run-budget", client=fake,
                               record_ledger=False)
    assert res.reasoning_source_type == ReasoningSourceType.LLM_BUDGET_BLOCKED
    assert res.ok is False
    assert len(fake.calls) == 0  # never called the model


@pytest.mark.unit
def test_llm_safety_block_falls_back(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan", safety_refuse=True)
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING,
                               prompt_template_id="dynamic_planner", user_prompt="plan",
                               required_keys=PLAN_KEYS, client=fake, record_ledger=False)
    assert res.reasoning_source_type == ReasoningSourceType.LLM_SAFETY_BLOCKED
    assert res.safety_status == "SAFETY_BLOCKED"


@pytest.mark.unit
def test_no_retry_loop_on_safety_block(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan", safety_refuse=True)
    llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                         user_prompt="plan", required_keys=PLAN_KEYS, client=fake, record_ledger=False)
    assert len(fake.calls) == 1  # exactly one attempt, no retry-around


@pytest.mark.unit
def test_llm_tool_error_falls_back(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan", raise_error=True)
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                               user_prompt="plan", required_keys=PLAN_KEYS, client=fake, record_ledger=False)
    assert res.reasoning_source_type == ReasoningSourceType.LLM_TOOL_ERROR


# ---- Ledger + redaction ----
@pytest.mark.integration
def test_llm_call_logged_without_full_prompt_by_default(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    monkeypatch.setenv("HELIXFORGE_LLM_STORE_FULL_PROMPTS", "false")
    fake = FakeLLMClient(response="plan")
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                               user_prompt="SENSITIVE_PROMPT_BODY plan", required_keys=PLAN_KEYS,
                               run_id="run-log", client=fake, record_ledger=True)
    from app.llm import replay_store
    call = replay_store.get_call(res.llm_call_id)
    assert call is not None
    assert call.get("full_user_prompt") is None
    assert call.get("full_system_prompt") is None


@pytest.mark.integration
def test_llm_persistence_recursively_redacts_and_rehashes(monkeypatch):
    from app.llm import replay_store

    secret = "sk-ant-persisted-secret-123456"
    run_id = f"run-redact-{uuid.uuid4().hex}"
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    monkeypatch.setenv("HELIXFORGE_LLM_STORE_FULL_PROMPTS", "true")
    res = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner",
        user_prompt=f"unique-{uuid.uuid4().hex}",
        required_keys=PLAN_KEYS,
        client=FakeLLMClient(response="plan"),
        record_ledger=False,
    )
    assert res.data is not None
    res.text += f" token={secret}"
    res.output_summary = f"authorization={secret}"
    res.data["nested"] = {"api_key": secret, "safe": "kept"}

    replay_store.persist_call(
        res, run_id, "project-redaction", None,
        full_system_prompt=f"system token={secret}",
        full_user_prompt=f"user api_key={secret}",
    )
    stored = replay_store.get_call(res.llm_call_id)
    assert stored is not None
    assert secret not in json.dumps(stored)
    assert stored["data"]["nested"]["api_key"] == "***REDACTED***"
    assert stored["data"]["nested"]["safe"] == "kept"
    assert replay_store.is_valid_recorded_output(stored) is True


@pytest.mark.integration
def test_llm_ledger_is_metadata_only(monkeypatch):
    run_id = f"run-ledger-metadata-{uuid.uuid4().hex}"
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    res = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner",
        user_prompt=f"metadata-only-{uuid.uuid4().hex}",
        required_keys=PLAN_KEYS,
        run_id=run_id,
        client=FakeLLMClient(response="plan"),
        record_ledger=True,
    )
    response = client.get("/api/llm/ledger", params={"run_id": run_id})
    assert response.status_code == 200
    call = next(item for item in response.json()["calls"] if item["id"] == res.llm_call_id)
    assert call["model"] == res.model
    for content_field in (
        "text", "data", "full_system_prompt", "full_user_prompt",
        "input_summary", "output_summary",
    ):
        assert content_field not in call


@pytest.mark.integration
def test_recorded_output_endpoint_requires_real_intact_output(monkeypatch):
    run_id = f"run-recorded-endpoint-{uuid.uuid4().hex}"
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    real = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner",
        user_prompt=f"recorded-endpoint-{uuid.uuid4().hex}",
        required_keys=PLAN_KEYS,
        run_id=run_id,
        client=FakeLLMClient(response="plan"),
        record_ledger=True,
    )
    response = client.get(f"/api/llm/recorded-output/{real.llm_call_id}")
    assert response.status_code == 200
    assert response.json()["reasoning_source_type"] == "RECORDED_LLM_OUTPUT"

    tampered = db.get("llm_calls", real.llm_call_id)
    assert tampered is not None
    tampered["output_hash"] = "sha256:tampered"
    db.insert("llm_calls", tampered)
    assert client.get(f"/api/llm/recorded-output/{real.llm_call_id}").status_code == 409

    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    fallback = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner",
        user_prompt=f"fallback-endpoint-{uuid.uuid4().hex}",
        required_keys=PLAN_KEYS,
        run_id=run_id,
        record_ledger=True,
    )
    assert client.get(f"/api/llm/recorded-output/{fallback.llm_call_id}").status_code == 409


@pytest.mark.unit
def test_llm_redacts_secrets(monkeypatch):
    from app.services.provenance import redact_secrets
    assert "sk-ant-" not in redact_secrets("key sk-ant-abc123def456ghi789")


# ---- Config endpoint masks key ----
@pytest.mark.integration
def test_llm_config_endpoint_masks_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecretvalue-1234")
    r = client.get("/api/llm/config")
    assert r.status_code == 200
    body = r.json()
    assert "supersecretvalue" not in str(body)
    assert body["api_key_present"] is True


@pytest.mark.integration
def test_llm_health_no_key_safe(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    r = client.get("/api/llm/health")
    assert r.status_code == 200
    body = r.json()
    assert body["safe"] is True
    assert body["llm_available"] is False


@pytest.mark.integration
def test_llm_test_endpoint_is_hard_deterministic_when_live_is_configured(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")

    def fail_if_client_is_resolved(_explicit):
        raise AssertionError("/api/llm/test must never resolve a live client")

    monkeypatch.setattr(llm_adapter, "_resolve_client", fail_if_client_is_resolved)
    response = client.post("/api/llm/test", json={"prompt": "deterministic probe"})
    assert response.status_code == 200
    assert response.json()["reasoning_source_type"] == "DETERMINISTIC_FALLBACK"
    assert response.json()["fallback_used"] is True


@pytest.mark.unit
def test_llm_per_call_cost_cap_blocks_before_client(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan")
    result = llm_adapter.call_llm(
        purpose=LLMCallPurpose.REPORT_SUMMARY,
        prompt_template_id="report_summary",
        user_prompt=f"cost-cap-{uuid.uuid4().hex}",
        client=fake,
        max_cost_usd=0.0,
        record_ledger=False,
    )
    assert result.reasoning_source_type == ReasoningSourceType.LLM_BUDGET_BLOCKED
    assert result.estimated_cost_usd > 0
    assert fake.calls == []


# ---- Replay ----
@pytest.mark.integration
def test_llm_replay_records_recorded_output(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan")
    prompt = "plan for replay test EGFR unique-12345"
    res = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                               user_prompt=prompt, required_keys=PLAN_KEYS, run_id="run-replay",
                               client=fake, record_ledger=True)
    assert res.ok
    # Now replay mode: no client, must serve recorded output.
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "RECORDED_HYBRID_REPLAY")
    res2 = llm_adapter.call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                                user_prompt=prompt, required_keys=PLAN_KEYS, run_id="run-replay",
                                record_ledger=False)
    assert res2.reasoning_source_type == ReasoningSourceType.RECORDED_LLM_OUTPUT
    assert res2.ok is True


@pytest.mark.integration
def test_llm_replay_without_run_id_fails_closed(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    prompt = "run-owned replay output must not become global"
    first = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner", user_prompt=prompt,
        required_keys=PLAN_KEYS, run_id="run-owned-replay",
        client=FakeLLMClient(response="plan"), record_ledger=True,
    )
    assert first.ok is True
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "RECORDED_HYBRID_REPLAY")
    replay = llm_adapter.call_llm(
        purpose=LLMCallPurpose.DYNAMIC_PLANNING,
        prompt_template_id="dynamic_planner", user_prompt=prompt,
        required_keys=PLAN_KEYS, run_id=None, record_ledger=False,
    )
    assert replay.ok is False
    assert replay.reasoning_source_type == ReasoningSourceType.DETERMINISTIC_FALLBACK


# ---- Router + cost guard ----
@pytest.mark.unit
def test_model_router_dev_uses_sonnet(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    r = model_router.route(LLMCallPurpose.DYNAMIC_PLANNING, LLMMode.HYBRID_LLM_DEV)
    assert r["model"] == "claude-sonnet-5"


@pytest.mark.unit
def test_model_router_final_uses_fable_for_reasoning_only(monkeypatch):
    hyp = model_router.route(LLMCallPurpose.HYPOTHESIS_REASONING, LLMMode.HYBRID_FABLE_FINAL)
    fmt = model_router.route(LLMCallPurpose.SAFE_REWRITE, LLMMode.HYBRID_FABLE_FINAL)
    assert hyp["model"] == "claude-fable-5"
    assert fmt["model"] != "claude-fable-5"  # routine work never Fable


@pytest.mark.unit
def test_cost_guard_blocks_over_budget(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_COST_PER_RUN_USD", "0.01")
    model_router._reset_all_for_tests()
    model_router.record_spend(0.02, run_id="r1", model="claude-fable-5", purpose="x")
    check = model_router.check_budget(0.01, "r1")
    assert check["allowed"] is False
    assert check["status"] == "BLOCKED_RUN"


@pytest.mark.unit
def test_cost_guard_reloads_complete_durable_ledger_without_list_page(monkeypatch):
    from app.models.schemas import utcnow

    run_id = "durable-budget-run"
    db.insert("llm_calls", {
        "id": "durable-budget-call", "run_id": run_id,
        "workflow_run_id": run_id, "created_at": utcnow(),
        "actual_cost_usd": 0.02,
    })
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_COST_PER_RUN_USD", "0.01")
    model_router._RUN_COST.clear()
    model_router._PERSISTED_LEDGER_LOADED = False
    # The restart guard must aggregate in SQLite, not read a bounded UI page.
    monkeypatch.setattr(db, "list_records", lambda *args, **kwargs: [])
    check = model_router.check_budget(0.001, run_id)
    assert check["allowed"] is False
    assert check["status"] == "BLOCKED_RUN"


@pytest.mark.unit
def test_cost_ledger_records_actual_usage(monkeypatch):
    model_router._reset_all_for_tests()
    model_router.record_spend(0.05, run_id="r2", model="claude-sonnet-5", purpose="planning")
    led = model_router.cost_ledger("r2")
    assert led["run_total_usd"] == 0.05
    assert "claude-sonnet-5" in led["by_model"]


@pytest.mark.unit
def test_session_reset_cannot_reset_run_or_daily_budget_counters():
    model_router.record_spend(0.01, run_id="reset-proof", model="m", purpose="p")
    result = model_router.reset_session()
    ledger = model_router.cost_ledger("reset-proof")
    assert result["budget_counters_preserved"] is True
    assert ledger["session_total_usd"] == 0.0
    assert ledger["run_total_usd"] == 0.01
    assert ledger["day_total_usd"] == 0.01


@pytest.mark.unit
def test_atomic_reservations_prevent_concurrent_budget_overcommit(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_LLM_MAX_COST_PER_RUN_USD", "0.01")
    first = model_router.reserve_budget(0.006, "reservation-run")
    second = model_router.reserve_budget(0.006, "reservation-run")
    assert first["allowed"] is True
    assert second["allowed"] is False
    model_router.release_reservation(first["reservation_id"])


# ---- Prompt templates ----
@pytest.mark.unit
def test_prompt_templates_exist():
    reg = prompt_templates.registry()
    ids = {t["id"] for t in reg}
    assert {"dynamic_planner", "hypothesis_reasoner", "semantic_critic", "safe_rewrite"}.issubset(ids)
    assert all(t["exists"] for t in reg)


@pytest.mark.unit
def test_prompt_templates_include_no_cot_and_no_synthesis_rule():
    sys = prompt_templates.system_prompt_for("hypothesis_reasoner").lower()
    assert "chain-of-thought" in sys
    assert "synthesis route" in sys


@pytest.mark.unit
def test_prompt_template_hash_recorded():
    h = prompt_templates.combined_hash("dynamic_planner")
    assert h.startswith("sha256:")


# ---- Live smoke gated off ----
@pytest.mark.integration
def test_live_smoke_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE", raising=False)
    r = client.post("/api/llm/live-smoke", json={})
    assert r.status_code == 200
    assert r.json()["ran"] is False


@pytest.mark.integration
@pytest.mark.parametrize("invalid_cap", [-0.01, "NaN", "Infinity"])
def test_live_smoke_rejects_nonfinite_or_negative_cost_cap(invalid_cap):
    response = client.post("/api/llm/live-smoke", json={"max_cost_usd": invalid_cap})
    assert response.status_code == 422


@pytest.mark.integration
def test_live_smoke_enforces_requested_cap_before_client_resolution(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE", "true")
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")

    def fail_if_client_is_resolved(_explicit):
        raise AssertionError("cost-capped smoke probe must not resolve a client")

    monkeypatch.setattr(llm_adapter, "_resolve_client", fail_if_client_is_resolved)
    response = client.post("/api/llm/live-smoke", json={"max_cost_usd": 0.0})
    assert response.status_code == 200
    body = response.json()
    assert body["ran"] is False
    assert body["estimated_cost_usd"] > body["max_cost_usd"]
    assert body["run_id"].startswith("llm-live-smoke-")


@pytest.mark.integration
def test_live_smoke_uses_scoped_run_and_passes_cost_cap(monkeypatch):
    from app.llm import replay_store

    monkeypatch.setenv("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE", "true")
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "true")
    monkeypatch.setenv("HELIXFORGE_LLM_MODE", "HYBRID_LLM_DEV")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-xxxx")
    fake = FakeLLMClient(response="plan")
    monkeypatch.setattr(llm_adapter, "_resolve_client", lambda _explicit: (fake, "fake"))

    response = client.post("/api/llm/live-smoke", json={"max_cost_usd": 0.05})
    assert response.status_code == 200
    body = response.json()
    assert body["ran"] is True
    assert body["run_id"].startswith("llm-live-smoke-")
    assert body["max_cost_usd"] == 0.05
    assert body["estimated_cost_usd"] <= body["max_cost_usd"]
    assert len(fake.calls) == 1
    stored = replay_store.get_call(body["llm_call_id"])
    assert stored is not None
    assert stored["run_id"] == body["run_id"]


@pytest.mark.live_llm
def test_live_smoke_runs_with_env_and_key():  # pragma: no cover - opt-in only
    import os
    if not (os.getenv("ANTHROPIC_API_KEY") and os.getenv("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE") == "true"):
        pytest.skip("live LLM smoke not enabled")
    r = client.post("/api/llm/live-smoke", json={"max_cost_usd": 0.05})
    assert r.status_code == 200
    assert r.json()["ran"] is True
