"""Data & Model Lab API (Phase 8 Priority 2): dataset curation, CPU QSAR baselines,
ligand-based screening, active-learning simulation, and CPU multi-objective search.
All CPU-only, no GPU/network/key required; degrades honestly if sklearn is absent."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import (
    active_learning, cpu_multiobjective, cpu_qsar, dataset_curation, ligand_screening,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["model-lab"])


def _resolve_run_project(run_id: str | None) -> str | None:
    if run_id is None:
        return None
    run = db.get("workflow_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="workflow run not found")
    project_id = run.get("project_id")
    if not project_id:
        raise HTTPException(status_code=409, detail="workflow run has no project")
    return project_id


# ---- Dataset curation ----
class CurateRequest(BaseModel):
    records: list[dict] = Field(default_factory=list)
    dataset_name: str = "dataset"
    source: Literal["user"] = "user"
    endpoint_type: str = "activity"
    license_status: str = "REVIEW_REQUIRED"
    exploratory: bool = False
    run_id: str | None = None


@router.post("/datasets/curate")
def curate(req: CurateRequest):
    # Public uploads are always human-provided. Only trusted server adapters may
    # mint REAL_TOOL_OUTPUT provenance.
    project_id = _resolve_run_project(req.run_id)
    return dataset_curation.curate(req.records, dataset_name=req.dataset_name, source="user",
                                   endpoint_type=req.endpoint_type, license_status=req.license_status,
                                   exploratory=req.exploratory, run_id=req.run_id,
                                   project_id=project_id)


@router.get("/datasets")
def list_datasets(run_id: str | None = None):
    project_id = _resolve_run_project(run_id)
    return {"datasets": dataset_curation.list_datasets(project_id, run_id)}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    ds = dataset_curation.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="dataset not found")
    return ds


@router.get("/datasets/{dataset_id}/quality")
def dataset_quality(dataset_id: str):
    ds = dataset_curation.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"dataset_id": dataset_id, "quality_score": ds["quality_score"],
            "quality_dimensions": ds["quality_dimensions"], "trainable": ds["trainable"],
            "blocking_gaps": ds["blocking_gaps"], "warnings": ds["warnings"]}


@router.get("/datasets/{dataset_id}/card")
def dataset_card(dataset_id: str):
    return dataset_curation.data_card(dataset_id)


# ---- CPU models ----
class TrainRequest(BaseModel):
    dataset: list[dict] = Field(default_factory=list)
    task: str = "classification"
    endpoint: str = "activity"
    model_family: str = "random_forest"
    run_id: str | None = None


@router.post("/cpu-models/train")
def train_model(req: TrainRequest):
    project_id = _resolve_run_project(req.run_id)
    return cpu_qsar.train(req.dataset, task=req.task, endpoint=req.endpoint,
                          model_family=req.model_family, run_id=req.run_id,
                          project_id=project_id)


@router.get("/cpu-models")
def list_models(run_id: str | None = None):
    project_id = _resolve_run_project(run_id)
    return {"models": cpu_qsar.list_models(run_id, project_id),
            "availability": cpu_qsar.available()}


@router.get("/cpu-models/{model_id}")
def get_model(model_id: str):
    m = cpu_qsar.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="model not found")
    return m


@router.get("/cpu-models/{model_id}/card")
def model_card(model_id: str):
    m = cpu_qsar.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="model not found")
    return {"model_id": model_id, "family": m["model_family"], "task": m["task"],
            "endpoint": m["endpoint"], "features": m["feature_method"], "split": m["split_strategy"],
            "metrics": m["metrics"], "uncertainty": m["uncertainty"], "checksum": m["checksum"],
            "validation_status": m["validation_status"], "package_versions": m["package_versions"],
            "source_type": m["source_type"], "limitations": m["limitations"]}


@router.get("/cpu-models/{model_id}/validation")
def model_validation(model_id: str):
    m = cpu_qsar.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="model not found")
    return {"model_id": model_id, "split_strategy": m["split_strategy"],
            "duplicate_leakage_count": m["duplicate_leakage_count"], "metrics": m["metrics"],
            "sample_size_warning": m["sample_size_warning"], "dataset_summary": m["dataset_summary"],
            "validation_status": m["validation_status"]}


class PredictRequest(BaseModel):
    smiles: list[str] = Field(default_factory=list)


@router.post("/cpu-models/{model_id}/predict")
def predict(model_id: str, req: PredictRequest):
    return cpu_qsar.predict(model_id, req.smiles)


# ---- Ligand screening ----
class ScreenRequest(BaseModel):
    candidates: list[str] = Field(default_factory=list)
    reference_ligands: list[str] = Field(default_factory=list)
    top_k: int = 10
    run_id: str | None = None
    target: str | None = None


@router.post("/ligand-screen/run")
def ligand_screen(req: ScreenRequest):
    project_id = _resolve_run_project(req.run_id)
    return ligand_screening.screen(req.candidates, req.reference_ligands, top_k=req.top_k,
                                   run_id=req.run_id, target=req.target,
                                   project_id=project_id)


@router.get("/ligand-screen/runs/{screen_id}")
def get_screen(screen_id: str):
    s = ligand_screening.get_screen(screen_id)
    if not s:
        raise HTTPException(status_code=404, detail="screen not found")
    return s


# ---- Active learning ----
class ALRequest(BaseModel):
    pool: list[dict] = Field(default_factory=list)
    strategy: str = "uncertainty"
    oracle_mode: str = "HELD_OUT_DATASET_LABEL"
    cycles: int = 4
    batch_size: int = 3
    initial_labeled: int = 4
    run_id: str | None = None


@router.post("/active-learning/run")
def active_learning_run(req: ALRequest):
    project_id = _resolve_run_project(req.run_id)
    return active_learning.run(req.pool, strategy=req.strategy, oracle_mode=req.oracle_mode,
                               cycles=req.cycles, batch_size=req.batch_size,
                               initial_labeled=req.initial_labeled, run_id=req.run_id,
                               project_id=project_id)


@router.get("/active-learning/runs")
def list_al_runs(run_id: str | None = None):
    project_id = _resolve_run_project(run_id)
    return {"runs": active_learning.list_runs(project_id, run_id)}


@router.get("/active-learning/runs/{al_id}")
def get_al_run(al_id: str):
    r = active_learning.get_run(al_id)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    return r


# ---- CPU multi-objective ----
class MultiObjRequest(BaseModel):
    molecules: list[dict] = Field(default_factory=list)
    recorded_gpu_molecules: list[dict] | None = None


@router.post("/optimization/cpu-multiobjective")
def cpu_multiobjective_run(req: MultiObjRequest):
    return cpu_multiobjective.analyze(req.molecules)


@router.post("/optimization/compare-backends")
def compare_backends(req: MultiObjRequest):
    return cpu_multiobjective.compare_backends(req.molecules, req.recorded_gpu_molecules)
