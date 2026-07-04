"""TDC adapter — real Therapeutics Data Commons (PyTDC).

Lists key ADME/Tox datasets and loads them with PyTDC (which downloads the real
dataset on first use). Returns real row counts, columns, split summary, and a
preview. If PyTDC is missing → CONFIGURED_BUT_NOT_RUN. If the dataset download
fails (e.g. no network) → TOOL_ERROR. Never fabricates dataset contents.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus

try:
    import tdc  # noqa: F401
    _TDC_OK = True
    _TDC_ERR = ""
except Exception as exc:  # pragma: no cover
    _TDC_OK = False
    _TDC_ERR = str(exc)

# name -> (PyTDC group module, class, endpoint description)
DATASETS: dict[str, dict[str, str]] = {
    "Caco2_Wang": {"group": "single_pred", "cls": "ADME", "task": "ADME", "endpoint": "Caco-2 permeability"},
    "Lipophilicity_AstraZeneca": {"group": "single_pred", "cls": "ADME", "task": "ADME", "endpoint": "Lipophilicity (logD)"},
    "Solubility_AqSolDB": {"group": "single_pred", "cls": "ADME", "task": "ADME", "endpoint": "Aqueous solubility (logS)"},
    "hERG": {"group": "single_pred", "cls": "Tox", "task": "Tox", "endpoint": "hERG blocker"},
    "AMES": {"group": "single_pred", "cls": "Tox", "task": "Tox", "endpoint": "Ames mutagenicity"},
    "DILI": {"group": "single_pred", "cls": "Tox", "task": "Tox", "endpoint": "Drug-induced liver injury"},
}


class TDCAdapter(ToolAdapter):
    id = "tdc"
    name = "TDC/PyTDC"
    category = "chemistry"
    required_config = ["PyTDC python package", "network for first-time dataset download"]
    mode = "local"

    def health_check(self) -> ToolHealth:
        if not _TDC_OK:
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.MISSING_DEPENDENCY, mode=self.mode,
                detail=f"PyTDC not importable: {_TDC_ERR}", required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.AVAILABLE, mode=self.mode,
            detail=f"PyTDC importable; {len(DATASETS)} ADME/Tox datasets registered (download on first load).",
            required_config=self.required_config,
        )

    def list_datasets(self) -> dict[str, Any]:
        return {
            "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value if _TDC_OK else SourceType.CONFIGURED_BUT_NOT_RUN.value,
            "installed": _TDC_OK,
            "datasets": [
                {"name": n, "task": d["task"], "group": d["group"], "endpoint": d["endpoint"],
                 "description": f"{d['endpoint']} — TDC {d['task']} benchmark"}
                for n, d in DATASETS.items()
            ],
        }

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        dataset = payload.get("dataset", "Caco2_Wang")
        summary = f'dataset="{dataset}"'
        if not _TDC_OK:
            return {
                "tool_name": self.name, "source": self.name,
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "input_summary": summary,
                "output_summary": "PyTDC not installed; dataset not loaded.",
                "validation_status": ValidationStatus.SKIPPED.value,
                "dataset_name": dataset, "task": "", "row_count": 0,
                "columns": [], "split_summary": {}, "preview": [],
                "errors": [], "warnings": [f"PyTDC unavailable: {_TDC_ERR}"],
            }
        if dataset not in DATASETS:
            return self._error(summary, [f"Unknown dataset '{dataset}'. Known: {', '.join(DATASETS)}"])

        meta = DATASETS[dataset]
        cache = get_settings().cache_dir
        Path(cache).mkdir(parents=True, exist_ok=True)
        try:
            from tdc.single_pred import ADME, Tox  # local import so import errors are caught
            cls = ADME if meta["cls"] == "ADME" else Tox
            data = cls(name=dataset, path=cache)
            df = data.get_data()
            split = data.get_split()
            preview = df.head(5).to_dict(orient="records")
            split_summary = {k: int(len(v)) for k, v in split.items()}
            columns = [str(c) for c in df.columns.tolist()]
            return {
                "tool_name": self.name, "source": self.name,
                "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "input_summary": summary,
                "output_summary": f"Loaded {dataset}: {len(df)} rows, splits {split_summary} (real PyTDC).",
                "validation_status": ValidationStatus.PASSED.value,
                "dataset_name": dataset, "task": meta["task"], "row_count": int(len(df)),
                "columns": columns, "split_summary": split_summary,
                "preview": _jsonable(preview), "errors": [], "warnings": [],
            }
        except Exception as exc:
            return self._error(summary, [f"TDC load failed (download/parse): {type(exc).__name__}: {exc}"])

    def _error(self, summary: str, errors: list[str]) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.TOOL_ERROR.value,
            "input_summary": summary,
            "output_summary": "TDC dataset load failed; no fabricated data returned.",
            "validation_status": ValidationStatus.FAILED.value,
            "dataset_name": "", "task": "", "row_count": 0,
            "columns": [], "split_summary": {}, "preview": [],
            "errors": errors, "warnings": [],
        }


def _jsonable(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        out.append({k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()})
    return out
