"""Generate the small, sanitized, committed built-in EGFR/NSCLC snapshot.

Runs a limited REAL agentic pipeline, captures it as a snapshot, and writes a
`builtin-egfr-nsclc.json` file (sanitized; dataset metadata only). Requires a
network connection at generation time; the resulting file is committed so the
app can replay it offline as RECORDED_REAL_TOOL_OUTPUT.

Usage:
    cd helixforge/backend && source .venv/bin/activate
    python -m app.scripts.make_builtin_snapshot
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services import agent_engine, snapshots


def main() -> None:
    print("Running a limited real EGFR/NSCLC pipeline (max_results=3)…")
    run = agent_engine.run_agentic_pipeline({
        "condition": "non-small cell lung cancer", "target_query": "EGFR",
        "max_results": 3, "create_reinvent_config": False, "error_injections": {},
    })
    print(f"  run {run['run_id']} status={run['status']} agents={len(run['agent_runs'])}")

    snap = snapshots.create_snapshot_from_run(
        run["run_id"], "Built-in EGFR/NSCLC recorded real snapshot",
        "Limited, sanitized, timestamped built-in snapshot (max_results=3).")
    payload = json.loads(Path(snap["storage_path"]).read_text())
    payload["_name"] = snap["name"]
    payload["_description"] = snap["description"]

    out = snapshots.SNAP_DIR / "builtin-egfr-nsclc.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    size_kb = out.stat().st_size / 1024
    print(f"  wrote {out} ({size_kb:.1f} KB)")
    if size_kb > 400:
        print("  WARNING: snapshot >400KB — consider trimming before committing.")


if __name__ == "__main__":
    main()
