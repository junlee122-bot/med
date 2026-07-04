#!/usr/bin/env python3
"""Repository hygiene check.

Fails (exit 1) if the repo would confuse a judge or leak artifacts:
- root README must point to helixforge/ as the official app
- no secrets / heavy artifacts committed
- the legacy SPA must be archived (not advertised as official)
- docker compose + helixforge/README present

Run: python scripts/check_repo_hygiene.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT).decode()
    return [l for l in out.splitlines() if l]


def main() -> int:
    files = tracked_files()
    problems: list[str] = []
    warnings: list[str] = []

    # 1. Root README points to helixforge/.
    readme = (ROOT / "README.md")
    if not readme.exists():
        problems.append("root README.md missing")
    else:
        text = readme.read_text()
        if "helixforge/" not in text:
            problems.append("root README.md does not point to helixforge/")
        if "official" not in text.lower():
            warnings.append("root README.md should clearly mark helixforge/ as official")

    # 2. No secrets / heavy artifacts committed.
    for f in files:
        if f == ".env" or f.endswith("/.env") or (f.startswith(".env.") and not f.endswith(".example")):
            problems.append(f"committed env file: {f}")
        if "/node_modules/" in f or f.startswith("node_modules/"):
            problems.append(f"committed node_modules: {f}")
        if "/.venv/" in f or "/venv/" in f:
            problems.append(f"committed venv: {f}")
        if f.endswith("helixforge.db") or f.endswith(".sqlite3"):
            problems.append(f"committed database: {f}")
        # user snapshots (snap-<hex>.json) must not be committed; builtin-*.json are OK
        base = f.rsplit("/", 1)[-1]
        if base.startswith("snap-") and base.endswith(".json"):
            problems.append(f"committed user snapshot: {f}")
        if f.endswith((".pkl", ".joblib", ".pt", ".pth", ".onnx")):
            warnings.append(f"committed model binary: {f}")

    # 3. Legacy SPA archived, not advertised as official.
    legacy = ROOT / "legacy-demo-spa"
    if legacy.exists():
        lr = legacy / "README.md"
        if not lr.exists() or "archived" not in lr.read_text().lower():
            problems.append("legacy-demo-spa/README.md must explain it is archived")
    # There must be no root-level package.json presenting a legacy app as main.
    if (ROOT / "package.json").exists():
        problems.append("root package.json present — legacy app may be advertised as official")

    # 4. Core files present.
    if not (ROOT / "helixforge" / "README.md").exists():
        problems.append("helixforge/README.md missing")
    if not (ROOT / "helixforge" / "docker-compose.yml").exists():
        problems.append("helixforge/docker-compose.yml missing")

    # 5. Built-in snapshot committed and small.
    builtins = list((ROOT / "helixforge" / "backend" / "data" / "snapshots").glob("builtin-*.json")) \
        if (ROOT / "helixforge" / "backend" / "data" / "snapshots").exists() else []
    for b in builtins:
        kb = b.stat().st_size / 1024
        if kb > 500:
            warnings.append(f"built-in snapshot large: {b.name} ({kb:.0f}KB)")

    print("=== Repo hygiene ===")
    for w in warnings:
        print(f"  WARN  {w}")
    for p in problems:
        print(f"  FAIL  {p}")
    if problems:
        print(f"HYGIENE: FAIL ({len(problems)} problem(s), {len(warnings)} warning(s))")
        return 1
    print(f"HYGIENE: PASS ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
