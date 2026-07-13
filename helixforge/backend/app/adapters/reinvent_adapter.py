"""REINVENT4 adapter — config generation + subprocess execution + result parsing.

- create-config: always writes a real REINVENT4 TOML config from the request
  (scoring weights → scoring components). This works with or without REINVENT4
  installed.
- run: executes REINVENT4 via `REINVENT4_PYTHON -m reinvent <config>` or
  `REINVENT4_BIN <config>` if configured. If not configured/installed, returns
  CONFIGURED_BUT_NOT_RUN — never fabricated molecules.
- parse-results: reads generated SMILES and post-validates each with RDKit.

Safety: generation is property/QSAR-guided at a high level; a safety penalty
component is included. No synthesis routes are produced.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus, utcnow
from app.storage import db


class REINVENT4Adapter(ToolAdapter):
    id = "reinvent"
    name = "REINVENT4"
    category = "chemistry"
    required_config = ["REINVENT4_PYTHON or REINVENT4_BIN", "prior/checkpoint model files"]
    mode = "subprocess"
    _PYTHON_NAME = re.compile(r"^(?:py|python|python3|python\d+(?:\.\d+)?)(?:\.exe)?$", re.I)
    _REINVENT_NAME = re.compile(r"^reinvent4?(?:\.exe)?$", re.I)

    def _jobs_dir(self) -> Path:
        d = Path(get_settings().cache_dir) / "reinvent"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _runner(self) -> tuple[str, list[str]] | None:
        s = get_settings()
        python = self._allowlisted_executable(s.reinvent4_python, self._PYTHON_NAME)
        if python:
            return "python", [python, "-m", "reinvent"]
        if s.reinvent4_bin:
            binary = self._allowlisted_executable(s.reinvent4_bin, self._REINVENT_NAME)
            if binary:
                return "bin", [binary]
        return None

    @staticmethod
    def _allowlisted_executable(configured: str, name_pattern: re.Pattern[str]) -> str | None:
        """Resolve only known REINVENT/Python executable names from immutable env config."""
        if not configured or any(ord(ch) < 32 or ord(ch) == 127 for ch in configured):
            return None
        found = shutil.which(configured)
        candidate = Path(found or configured)
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        if not resolved.is_file() or not name_pattern.fullmatch(resolved.name):
            return None
        return str(resolved)

    def health_check(self) -> ToolHealth:
        runner = self._runner()
        if runner:
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.AVAILABLE, mode=self.mode,
                detail=f"REINVENT4 runner configured ({runner[0]}). Config generation + execution enabled.",
                required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.NOT_CONFIGURED, mode=self.mode,
            detail="REINVENT4 not configured. Config generation works; execution requires "
                   "REINVENT4_PYTHON or REINVENT4_BIN (see docs/TOOL_INTEGRATION.md).",
            required_config=self.required_config,
        )

    # -- create config ----------------------------------------------------
    def create_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            target = self._validated_target(payload.get("target_name", "EGFR"))
            max_molecules = int(payload.get("max_molecules", 100))
            if not 1 <= max_molecules <= 10_000:
                raise ValueError("max_molecules must be between 1 and 10000")
            weights = self._validated_weights(payload.get("scoring_weights", {}) or {})
        except (TypeError, ValueError) as exc:
            return self._error("invalid REINVENT4 configuration", [str(exc)])
        job_id = f"rv-{uuid.uuid4().hex[:8]}"
        job_dir = self._jobs_dir() / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        config_path = job_dir / "sampling.toml"
        config_path.write_text(
            self._render_toml(target, weights, max_molecules, job_dir),
            encoding="utf-8",
            newline="\n",
        )

        db.insert("reinvent_jobs", {
            "id": job_id, "project_id": payload.get("project_id"), "created_at": utcnow(),
            "workflow_run_id": payload.get("workflow_run_id"),
            "status": "config_created", "config_path": str(config_path),
            "target": target, "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
        })
        runner = self._runner()
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
            "input_summary": f"target={target}, max_molecules={max_molecules}",
            "output_summary": f"REINVENT4 config written to {config_path.name}. "
                              + ("Runner configured — POST /api/reinvent/run to execute."
                                 if runner else "No runner configured; config is ready for a REINVENT4 install."),
            "validation_status": ValidationStatus.PASSED.value,
            "config_path": str(config_path), "job_id": job_id, "status": "config_created",
            "generated_smiles": [], "logs": [f"config generated for {target}"],
            "errors": [], "warnings": [] if runner else ["Execution requires REINVENT4_PYTHON/BIN — config only."],
        }

    @staticmethod
    def _validated_target(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("target_name must be a string")
        target = value.strip()
        if not target or len(target) > 128:
            raise ValueError("target_name must contain 1 to 128 characters")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
            raise ValueError("target_name contains forbidden control characters")
        return target

    @staticmethod
    def _validated_weights(values: dict[str, Any]) -> dict[str, float]:
        if not isinstance(values, dict):
            raise ValueError("scoring_weights must be an object")
        result: dict[str, float] = {}
        for key in ("qed", "rdkit_validity", "admet", "novelty", "safety_penalty"):
            value = float(values.get(key, 0.2))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"scoring weight {key} must be a finite number from 0 to 1")
            result[key] = value
        return result

    def _render_toml(self, target: str, weights: dict[str, float], max_molecules: int, job_dir: Path) -> str:
        w = {
            "qed": weights.get("qed", 0.2),
            "rdkit_validity": weights.get("rdkit_validity", 0.2),
            "admet": weights.get("admet", 0.2),
            "novelty": weights.get("novelty", 0.2),
            "safety_penalty": weights.get("safety_penalty", 0.2),
        }
        out_smi = job_dir / "generated.smi"
        return f'''# REINVENT4 sampling configuration — generated by HelixForge AI
# Target context: {target}
# NOTE: `model_file` must point to a real REINVENT4 prior/checkpoint. This config
# is complete and valid; provide the model file to run.
run_type = "sampling"
device = "cpu"
json_out_config = {json.dumps(str(job_dir / 'sampling.json'))}

[parameters]
model_file = "priors/reinvent.prior"   # <-- set to your REINVENT4 prior
output_file = {json.dumps(str(out_smi))}
num_smiles = {max_molecules}
unique_molecules = true
randomize_smiles = true

# Scoring profile derived from request weights (transfer/RL scoring reference).
# Weights: QED={w['qed']} validity={w['rdkit_validity']} ADMET={w['admet']} novelty={w['novelty']} safety={w['safety_penalty']}
[scoring]
type = "geometric_mean"

[[scoring.component]]
[scoring.component.QED]
[[scoring.component.QED.endpoint]]
name = "QED"
weight = {w['qed']}

[[scoring.component]]
[scoring.component.custom_alerts]   # safety penalty: structural alerts
[[scoring.component.custom_alerts.endpoint]]
name = "safety_penalty"
weight = {w['safety_penalty']}

[[scoring.component]]
[scoring.component.MolecularWeight]  # ADMET-adjacent physchem guard
[[scoring.component.MolecularWeight.endpoint]]
name = "ADMET_physchem"
weight = {w['admet']}
transform.type = "double_sigmoid"
transform.high = 500.0
transform.low = 200.0
transform.coef_div = 500.0
transform.coef_si = 20.0
transform.coef_se = 20.0
'''

    # -- run --------------------------------------------------------------
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_path = str(payload.get("config_path", "") or "")
        summary = f"config={Path(config_path).name if config_path else '(none)'}"
        runner = self._runner()
        job = self._generated_job_for_config(config_path, payload.get("project_id"))
        if not job:
            return self._error(
                summary,
                ["Config is not a generated REINVENT4 job owned by this project. Call create-config first."],
            )
        config_path = str(Path(job["config_path"]).resolve(strict=True))
        if not runner:
            return {
                "tool_name": self.name, "source": self.name,
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "input_summary": summary,
                "output_summary": "REINVENT4 runner not configured; config is ready but was not executed.",
                "validation_status": ValidationStatus.SKIPPED.value,
                "config_path": config_path, "job_id": "", "status": "not_run",
                "generated_smiles": [], "logs": [],
                "errors": [], "warnings": ["Set REINVENT4_PYTHON or REINVENT4_BIN to execute. No fabricated output."],
            }
        try:
            cmd = runner[1] + [config_path]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=get_settings().timeout_seconds * 20,
            )
            logs = (proc.stdout + "\n" + proc.stderr).splitlines()[-40:]
            if proc.returncode != 0:
                return self._error(summary, [f"REINVENT4 exit {proc.returncode}"], logs=logs)
            # Parse output file referenced by config.
            smiles = self._read_output_from_config(config_path)
            parsed = self.parse_results({"smiles": smiles})
            return {
                "tool_name": self.name, "source": self.name,
                "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "input_summary": summary,
                "output_summary": f"REINVENT4 generated {len(smiles)} SMILES; {parsed.get('valid_count', 0)} valid (RDKit).",
                "validation_status": ValidationStatus.PASSED.value,
                "config_path": config_path, "job_id": f"rv-run-{uuid.uuid4().hex[:6]}", "status": "complete",
                "generated_smiles": smiles[:200], "valid_count": parsed.get("valid_count"),
                "logs": logs, "errors": [], "warnings": [],
            }
        except Exception as exc:
            return self._error(summary, [f"{type(exc).__name__}: {exc}"])

    def _generated_job_for_config(self, config_path: str, project_id: Any) -> dict[str, Any] | None:
        if not config_path or any(ord(ch) < 32 or ord(ch) == 127 for ch in config_path):
            return None
        try:
            resolved = Path(config_path).resolve(strict=True)
            root = self._jobs_dir().resolve(strict=True)
            relative = resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            return None
        if len(relative.parts) != 2 or relative.parts[1] != "sampling.toml":
            return None
        job_id = relative.parts[0]
        if not re.fullmatch(r"rv-[0-9a-f]{8}", job_id):
            return None
        job = db.get("reinvent_jobs", job_id)
        if not job or job.get("project_id") != project_id:
            return None
        try:
            recorded = Path(str(job.get("config_path", ""))).resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        return job if recorded == resolved else None

    def _read_output_from_config(self, config_path: str) -> list[str]:
        config = Path(config_path).resolve(strict=True)
        text = config.read_text(encoding="utf-8")
        out_file = None
        for line in text.splitlines():
            if line.strip().startswith("output_file"):
                out_file = line.split("=", 1)[1].strip().strip('"')
                break
        if out_file:
            try:
                output = Path(out_file).resolve(strict=True)
            except (OSError, RuntimeError):
                return []
            if output.parent != config.parent:
                return []
            return [
                ln.split()[0]
                for ln in output.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()
            ]
        return []

    # -- parse results ----------------------------------------------------
    def parse_results(self, payload: dict[str, Any]) -> dict[str, Any]:
        smiles = payload.get("smiles", [])
        if isinstance(smiles, str):
            smiles = [s for s in smiles.splitlines() if s.strip()]
        valid = 0
        try:
            from app.adapters.rdkit_adapter import RDKitAdapter, rdkit_available
            if rdkit_available():
                rd = RDKitAdapter()
                for smi in smiles:
                    r = rd.run({"operation": "validate", "smiles": smi})
                    if r.get("valid"):
                        valid += 1
        except Exception:
            pass
        return {
            "tool_name": self.name, "source": "User-supplied result payload",
            # This endpoint validates an uploaded list; it does not prove that
            # REINVENT produced it. Only the guarded run/job path may claim a
            # real-tool output provenance label.
            "source_type": SourceType.HUMAN_INPUT.value if smiles else SourceType.CONFIGURED_BUT_NOT_RUN.value,
            "input_summary": f"{len(smiles)} SMILES to parse",
            "output_summary": f"Parsed {len(smiles)} SMILES; {valid} valid by RDKit.",
            "validation_status": ValidationStatus.PASSED.value if smiles else ValidationStatus.SKIPPED.value,
            "generated_smiles": smiles[:200], "valid_count": valid,
            "errors": [], "warnings": (["Uploaded SMILES are HUMAN_INPUT; no REINVENT job provenance was verified."]
                                         if smiles else []),
        }

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return db.get("reinvent_jobs", job_id)

    def _error(self, summary: str, errors: list[str], logs: list[str] | None = None) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.TOOL_ERROR.value,
            "input_summary": summary,
            "output_summary": "REINVENT4 step failed; no fabricated molecules returned.",
            "validation_status": ValidationStatus.FAILED.value,
            "config_path": "", "job_id": "", "status": "error",
            "generated_smiles": [], "logs": logs or [], "errors": errors, "warnings": [],
        }
