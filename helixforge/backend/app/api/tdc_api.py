from __future__ import annotations

from fastapi import APIRouter

from app.adapters import registry as reg
from app.models.schemas import TDCDatasetsResponse, TDCLoadRequest, TDCResponse

router = APIRouter(prefix="/api/tdc", tags=["tdc"])


@router.get("/datasets", response_model=TDCDatasetsResponse)
def datasets():
    return TDCDatasetsResponse(**reg.tdc.list_datasets())


@router.post("/load", response_model=TDCResponse)
def load(req: TDCLoadRequest):
    out = reg.tdc.execute(req.model_dump(), project_id=req.project_id)
    return TDCResponse(**out)


@router.post("/benchmark-summary", response_model=TDCResponse)
def benchmark_summary(req: TDCLoadRequest):
    """Benchmark metadata derived from the real loaded dataset (split sizes, columns)."""
    out = reg.tdc.execute(req.model_dump(), project_id=req.project_id)
    if out.get("row_count"):
        splits = out.get("split_summary", {})
        out["output_summary"] = (
            f"Benchmark surface for {out.get('dataset_name')}: {out.get('row_count')} rows; "
            f"train/valid/test = {splits.get('train',0)}/{splits.get('valid',0)}/{splits.get('test',0)}; "
            f"columns {out.get('columns')}. Use as an evaluation reference."
        )
    return TDCResponse(**out)
