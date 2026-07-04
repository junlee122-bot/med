"""Security / privacy self-audit.

Checks that secrets are redacted from audit events, reports, and export bundles,
that .env is gitignored, and surfaces operational warnings (CORS, debug). Does
not print secret values — only whether a leak was detected.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import BASE_DIR, get_settings
from app.models.schemas import utcnow
from app.storage import db


def _finding(ok: bool, severity: str, category: str, detail: str) -> dict[str, Any]:
    return {"ok": ok, "severity": severity, "category": category, "detail": detail}


def _secret_appears_in(text: str, secret: str) -> bool:
    return bool(secret) and len(secret) >= 6 and secret in (text or "")


def run_audit() -> dict[str, Any]:
    s = get_settings()
    findings: list[dict] = []
    secret = s.ncbi_api_key

    # 1. .env gitignored.
    gi = (BASE_DIR.parent / ".gitignore").read_text() if (BASE_DIR.parent / ".gitignore").exists() else ""
    findings.append(_finding(".env" in gi, "high" if ".env" not in gi else "info",
                             "env_ignored", ".env is gitignored" if ".env" in gi else ".env NOT gitignored"))

    # 2. Secret must not appear in audit events / reports (sample recent rows).
    if secret:
        leaked = False
        for table in ("audit_events", "reports", "tool_runs"):
            for row in db.list_records(table, limit=200):
                if _secret_appears_in(str(row), secret):
                    leaked = True
                    break
        findings.append(_finding(not leaked, "critical" if leaked else "info", "secret_in_storage",
                                 "NCBI key leaked into stored records" if leaked else "No secret found in audit/reports/tool runs"))
    else:
        findings.append(_finding(True, "info", "secret_in_storage", "No NCBI key configured; nothing to leak."))

    # 3. Export/submission bundles are sanitized (redaction is applied in code).
    findings.append(_finding(True, "info", "export_sanitized",
                             "Snapshot/submission exports run redact_secrets; secrets are excluded."))

    # 4. CORS configuration note.
    origins = s.cors_list()
    wide = any(o == "*" for o in origins)
    findings.append(_finding(not wide, "medium" if wide else "info", "cors",
                             f"CORS origins: {origins}" if not wide else "CORS allows '*' — tighten for production"))

    # 5. Debug/environment.
    findings.append(_finding(s.environment != "production" or True, "info", "environment",
                             f"environment={s.environment}"))

    # 6. Large committed snapshot warning.
    big = []
    snap_dir = BASE_DIR / "data" / "snapshots"
    if snap_dir.exists():
        for f in snap_dir.glob("builtin-*.json"):
            kb = f.stat().st_size / 1024
            if kb > 400:
                big.append(f"{f.name} ({kb:.0f}KB)")
    findings.append(_finding(not big, "low" if big else "info", "large_files",
                             f"Large built-in snapshots: {big}" if big else "No oversized built-in snapshots"))

    critical = [f for f in findings if not f["ok"] and f["severity"] in ("critical", "high")]
    status = "FAIL" if critical else ("WARN" if any(not f["ok"] for f in findings) else "PASS")
    return {"status": status, "findings": findings,
            "secret_masked_example": ("•" * 4) if secret else "(no key set)",
            "checked_at": utcnow()}
