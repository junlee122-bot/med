"""Test isolation: run the suite against a clean, temporary data directory.

Without this, the persistent `backend/data/helixforge.db` accumulates rows across
runs, which makes order/limit-sensitive assertions (e.g. governance audits that
cap their result lists) flaky. We redirect HELIXFORGE_DATA_DIR to a temp dir
BEFORE any `app.*` import so config resolves the DB + snapshot paths there, and we
copy the committed built-in snapshot in so record/replay tests still find it.

Honors a caller-provided HELIXFORGE_DATA_DIR (CI can pin its own).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

if not os.getenv("HELIXFORGE_DATA_DIR"):
    _tmp = Path(tempfile.mkdtemp(prefix="helixforge-test-"))
    os.environ["HELIXFORGE_DATA_DIR"] = str(_tmp)
    # Carry the committed built-in snapshot into the isolated data dir.
    _src = Path(__file__).resolve().parent.parent.parent / "data" / "snapshots"
    _dst = _tmp / "snapshots"
    _dst.mkdir(parents=True, exist_ok=True)
    if _src.exists():
        for f in _src.glob("builtin-*.json"):
            shutil.copy2(f, _dst / f.name)
        for extra in ("README.md", ".gitkeep"):
            p = _src / extra
            if p.exists():
                shutil.copy2(p, _dst / extra)
