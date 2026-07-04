"""AutoDock Vina adapter — fixture-based docking / scoring.

Runs Vina against pre-prepared receptor/ligand PDBQT fixtures shipped under
backend/fixtures/vina/. Uses the `vina` python package if importable, else the
`vina` CLI (configurable via VINA_BIN). If neither is available the job is
recorded as CONFIGURED_BUT_NOT_RUN — never a fabricated docking score.

Scope: fixture-based only. Arbitrary receptor preparation (protonation, grid
box definition, PDBQT conversion) is deliberately out of scope and flagged as
future work. No wet-lab or synthesis guidance is produced.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import BASE_DIR, get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus
from app.storage import db
from app.models.schemas import utcnow

FIXTURE_DIR = BASE_DIR / "fixtures" / "vina"

try:
    import vina as _vina_pkg  # noqa: F401
    _VINA_PY = True
except Exception:
    _VINA_PY = False


class VinaAdapter(ToolAdapter):
    id = "vina"
    name = "AutoDock Vina"
    category = "structure"
    required_config = ["vina python package OR VINA_BIN (CLI)", "receptor/ligand PDBQT fixtures"]
    mode = "fixture"

    def _cli_available(self) -> bool:
        return shutil.which(get_settings().vina_bin) is not None

    def health_check(self) -> ToolHealth:
        have_fixtures = FIXTURE_DIR.exists() and any(FIXTURE_DIR.glob("*.pdbqt"))
        if _VINA_PY or self._cli_available():
            status = HealthStatus.AVAILABLE if have_fixtures else HealthStatus.DEGRADED
            engine = "python(vina)" if _VINA_PY else f"cli({get_settings().vina_bin})"
            detail = f"Vina engine present [{engine}]." + ("" if have_fixtures else " No PDBQT fixtures found.")
            return ToolHealth(tool_id=self.id, name=self.name, category=self.category, status=status,
                              mode=self.mode, detail=detail, required_config=self.required_config)
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.NOT_CONFIGURED, mode=self.mode,
            detail="AutoDock Vina not installed (no python `vina`, no CLI). Fixtures present: "
                   f"{have_fixtures}. Install Vina to enable fixture docking (see docs/TOOL_INTEGRATION.md).",
            required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = f"vina-{uuid.uuid4().hex[:8]}"
        receptor = FIXTURE_DIR / payload.get("receptor_fixture", "sample_receptor.pdbqt")
        ligand = FIXTURE_DIR / payload.get("ligand_fixture", "sample_ligand.pdbqt")
        center = payload.get("center", [0, 0, 0])
        box = payload.get("box_size", [20, 20, 20])
        exhaustiveness = int(payload.get("exhaustiveness", 8))
        summary = f"receptor={receptor.name}, ligand={ligand.name}, exh={exhaustiveness}"

        engine_available = _VINA_PY or self._cli_available()
        if not engine_available:
            self._persist_job(job_id, "not_run", summary, [], SourceType.CONFIGURED_BUT_NOT_RUN, payload)
            return self._envelope(
                job_id, "not_run", SourceType.CONFIGURED_BUT_NOT_RUN, summary,
                out="Vina engine not installed; docking not executed.",
                warnings=["AutoDock Vina unavailable — install python `vina` or set VINA_BIN. No fabricated score."],
                validation=ValidationStatus.SKIPPED,
            )

        missing = [p.name for p in (receptor, ligand) if not p.exists()]
        if missing:
            self._persist_job(job_id, "error", summary, [], SourceType.TOOL_ERROR, payload)
            return self._envelope(
                job_id, "error", SourceType.TOOL_ERROR, summary,
                out="Required PDBQT fixture(s) missing; no docking performed.",
                errors=[f"Missing fixtures: {', '.join(missing)}. Place prepared PDBQT files under {FIXTURE_DIR}."],
                validation=ValidationStatus.FAILED,
            )

        # Real docking (python API preferred, else CLI).
        try:
            if _VINA_PY:
                scores, logs = self._dock_python(str(receptor), str(ligand), center, box, exhaustiveness, job_id)
            else:
                scores, logs = self._dock_cli(str(receptor), str(ligand), center, box, exhaustiveness, job_id)
        except Exception as exc:
            self._persist_job(job_id, "error", summary, [], SourceType.TOOL_ERROR, payload)
            return self._envelope(job_id, "error", SourceType.TOOL_ERROR, summary,
                                  out="Vina execution failed.", errors=[f"{type(exc).__name__}: {exc}"],
                                  validation=ValidationStatus.FAILED, logs=logs if 'logs' in dir() else [])
        self._persist_job(job_id, "complete", summary, scores, SourceType.REAL_TOOL_OUTPUT, payload)
        return self._envelope(
            job_id, "complete", SourceType.REAL_TOOL_OUTPUT, summary,
            out=f"Docking complete; best score {min(scores) if scores else 'NA'} kcal/mol (real Vina).",
            scores=scores, logs=logs, validation=ValidationStatus.PASSED,
            output_files=[f"{job_id}_out.pdbqt"],
        )

    # -- engines ----------------------------------------------------------
    def _dock_python(self, receptor, ligand, center, box, exh, job_id):
        from vina import Vina
        v = Vina(sf_name="vina")
        v.set_receptor(receptor)
        v.set_ligand_from_file(ligand)
        v.compute_vina_maps(center=[float(c) for c in center], box_size=[float(b) for b in box])
        v.dock(exhaustiveness=exh, n_poses=5)
        energies = v.energies(n_poses=5)
        scores = [round(float(row[0]), 3) for row in energies]
        return scores, [f"[vina-python] docked {ligand} into {receptor}", f"poses={len(scores)}"]

    def _dock_cli(self, receptor, ligand, center, box, exh, job_id):
        s = get_settings()
        out_path = FIXTURE_DIR / f"{job_id}_out.pdbqt"
        cmd = [
            s.vina_bin, "--receptor", receptor, "--ligand", ligand,
            "--center_x", str(center[0]), "--center_y", str(center[1]), "--center_z", str(center[2]),
            "--size_x", str(box[0]), "--size_y", str(box[1]), "--size_z", str(box[2]),
            "--exhaustiveness", str(exh), "--out", str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=s.timeout_seconds * 4)
        logs = (proc.stdout + "\n" + proc.stderr).splitlines()
        scores = []
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                try:
                    scores.append(round(float(parts[1]), 3))
                except ValueError:
                    pass
        if proc.returncode != 0 and not scores:
            raise RuntimeError(f"vina CLI exit {proc.returncode}: {proc.stderr[:200]}")
        return scores, logs[-20:]

    # -- persistence ------------------------------------------------------
    def _persist_job(self, job_id, status, summary, scores, source_type, payload):
        db.insert("docking_jobs", {
            "id": job_id, "project_id": payload.get("project_id"), "created_at": utcnow(),
            "status": status, "input_summary": summary, "scores": scores,
            "source_type": source_type.value,
        })

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return db.get("docking_jobs", job_id)

    def _envelope(self, job_id, status, source_type, summary, *, out, scores=None, logs=None,
                  output_files=None, errors=None, warnings=None, validation=ValidationStatus.SKIPPED):
        return {
            "tool_name": self.name, "source": self.name, "source_type": source_type.value,
            "input_summary": summary, "output_summary": out,
            "validation_status": validation.value,
            "job_id": job_id, "status": status, "scores": scores or [],
            "output_files": output_files or [], "logs": logs or [],
            "errors": errors or [], "warnings": warnings or [],
        }
