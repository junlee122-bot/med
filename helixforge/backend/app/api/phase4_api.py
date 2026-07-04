from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import (
    hwpx_handoff, red_team, rubric_scorecard, run_config, scientific_plausibility,
)

router = APIRouter(prefix="/api", tags=["phase4"])


# ---- Rubric scorecard ----
@router.get("/rubric/scorecard")
def rubric_scorecard_get():
    return rubric_scorecard.compute()


@router.post("/rubric/scorecard/persist")
def rubric_scorecard_persist():
    return rubric_scorecard.persist()


# ---- Scientific plausibility ----
@router.get("/plausibility/check")
def plausibility_check(run_id: str | None = None):
    return scientific_plausibility.check_run(run_id)


# ---- HWPX handoff ----
@router.get("/hwpx/handoff")
def hwpx_handoff_get():
    return hwpx_handoff.build_handoff()


# ---- Red-team suite ----
@router.get("/red-team/run")
def red_team_run():
    return red_team.run_suite()


# ---- New Run wizard ----
@router.get("/run-configs")
def run_configs():
    return run_config.list_configs()


class RunConfigValidateRequest(BaseModel):
    project_id: str | None = None
    target_query: str = Field(default="EGFR")
    condition: str = Field(default="non-small cell lung cancer")
    max_results: int = 8
    evaluation_mode: str = "retrospective_rediscovery"
    run_vina_fixture: bool = False
    create_reinvent_config: bool = True
    error_injections: dict[str, bool] = Field(default_factory=dict)


@router.post("/run-configs/validate")
def run_configs_validate(req: RunConfigValidateRequest):
    return run_config.validate(req.model_dump())
