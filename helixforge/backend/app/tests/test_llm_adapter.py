"""Phase 7 — LLM adapter: no-key fallback, budget, safety, schema, ledger, router.
All offline (deterministic FakeLLMClient); no live API calls."""
import pytest
from fastapi.testclient import TestClient

from app.llm import llm_adapter, model_router, prompt_templates
from app.llm.config import get_llm_config
from app.llm.schemas import LLMCallPurpose, LLMMode, ReasoningSourceType
from app.main import app
from app.tests.fakes.fake_llm_client import FakeLLMClient

client = TestClient(app)
PLAN_KEYS = ["objective", "selected_stages"]


@pytest.fixture(autouse=True)
def _reset_costs():
    model_router.reset_session()
    yield


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
    model_router.reset_session()
    model_router.record_spend(0.02, run_id="r1", model="claude-fable-5", purpose="x")
    check = model_router.check_budget(0.01, "r1")
    assert check["allowed"] is False
    assert check["status"] == "BLOCKED_RUN"


@pytest.mark.unit
def test_cost_ledger_records_actual_usage(monkeypatch):
    model_router.reset_session()
    model_router.record_spend(0.05, run_id="r2", model="claude-sonnet-5", purpose="planning")
    led = model_router.cost_ledger("r2")
    assert led["run_total_usd"] == 0.05
    assert "claude-sonnet-5" in led["by_model"]


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


@pytest.mark.live_llm
def test_live_smoke_runs_with_env_and_key():  # pragma: no cover - opt-in only
    import os
    if not (os.getenv("ANTHROPIC_API_KEY") and os.getenv("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE") == "true"):
        pytest.skip("live LLM smoke not enabled")
    r = client.post("/api/llm/live-smoke", json={"max_cost_usd": 0.05})
    assert r.status_code == 200
    assert r.json()["ran"] is True
