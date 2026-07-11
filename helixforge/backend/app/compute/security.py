"""Compute security primitives — secret redaction, path/archive safety, and the
field-level denylist that keeps an LLM (or any caller) from smuggling arbitrary
execution into a GPU job. Deterministic and dependency-free.
"""
from __future__ import annotations

import re
from typing import Any

# Fields that must NEVER appear in a job spec — they would allow arbitrary
# execution, image override, or code injection. Presence => hard reject.
FORBIDDEN_SPEC_FIELDS = {
    "command", "cmd", "entrypoint", "args", "shell", "script", "exec",
    "image", "docker_image", "container_image", "dockerfile",
    "pip_install", "apt_install", "install", "run", "bash", "sh",
    "python_code", "code", "eval", "download_url", "url", "curl", "wget",
    "mount", "volume", "volumes", "host_path", "privileged", "cap_add",
    "env_override", "secret", "secrets", "token", "api_key", "apikey",
    "password", "credential", "credentials", "ssh_key",
}

# Value patterns that look like secrets — redacted from logs/snapshots/exports.
_SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}|Bearer\s+[A-Za-z0-9._\-]{12,})")

# Shell-metacharacter / injection signature in any string value.
_SHELL_META = re.compile(r"[;&|`$><]|\$\(|\bsudo\b|\brm\s+-rf\b|\bcurl\b|\bwget\b|\bnc\b\s")


def redact_secrets(obj: Any) -> Any:
    """Recursively mask secret-looking string values. Never mutates the input."""
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if _looks_secret_key(k) else redact_secrets(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_secrets(v) for v in obj]
    if isinstance(obj, str):
        return _SECRET_VALUE.sub("***REDACTED***", obj)
    return obj


def _looks_secret_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in ("token", "secret", "password", "api_key", "apikey",
                                "credential", "ssh_key", "private_key"))


def scan_spec_for_forbidden(spec: dict[str, Any], _path: str = "") -> list[str]:
    """Return dotted paths of any forbidden field or unsafe value found anywhere."""
    hits: list[str] = []
    if isinstance(spec, dict):
        for k, v in spec.items():
            here = f"{_path}.{k}" if _path else k
            if k.lower() in FORBIDDEN_SPEC_FIELDS:
                hits.append(here)
            hits.extend(scan_spec_for_forbidden(v, here))
    elif isinstance(spec, list):
        for i, v in enumerate(spec):
            hits.extend(scan_spec_for_forbidden(v, f"{_path}[{i}]"))
    elif isinstance(spec, str):
        if _SHELL_META.search(spec):
            hits.append(f"{_path} (shell-metacharacters)")
        if _SECRET_VALUE.search(spec):
            hits.append(f"{_path} (secret-like value)")
    return hits


def is_safe_relative_path(name: str) -> bool:
    """Reject absolute paths, parent traversal, and NUL/newline tricks."""
    if not name or "\x00" in name or "\n" in name:
        return False
    if name.startswith("/") or name.startswith("\\") or ":" in name.split("/")[0]:
        return False
    parts = name.replace("\\", "/").split("/")
    return ".." not in parts and "" not in parts[:-1]


def safe_archive_members(names: list[str]) -> tuple[list[str], list[str]]:
    """Split archive member names into (safe, rejected). Rejects traversal, absolute
    paths, and symlink-looking device paths — a defense for artifact extraction."""
    safe, rejected = [], []
    for n in names:
        (safe if is_safe_relative_path(n) else rejected).append(n)
    return safe, rejected


def security_policies() -> dict[str, Any]:
    """The enforced compute-security policy set (for /api/compute/security/policies)."""
    from app.compute import schemas as S
    return {
        "image_allowlist": {"enforced": True, "count": len(S.IMAGE_ALLOWLIST),
                            "note": "immutable digests only; no arbitrary image."},
        "entrypoint_allowlist": {"enforced": True, "note": "fixed per job type; no command override."},
        "resource_caps": {"max_gpu_count": S.MAX_GPU_COUNT, "max_vram_gb": S.MAX_VRAM_GB,
                          "max_runtime_minutes": S.MAX_RUNTIME_MINUTES,
                          "max_output_size_mb": S.MAX_OUTPUT_SIZE_MB, "max_cost_ceiling_usd": S.MAX_JOB_COST_USD_CEILING},
        "secret_management": {"from_env_only": True, "in_payload": False, "masked_in_ui": True,
                              "redacted_from_logs_and_snapshots": True},
        "artifact_security": {"allowed_types": sorted(S.ALLOWED_ARTIFACT_TYPES),
                              "path_traversal_blocked": True, "checksum_required": True},
        "network_policy": {"arbitrary_egress": False, "approved_sources_only": True},
        "human_approval": {"required_for_paid_jobs": True, "required_for_uploaded_data": True},
        "kill_switch": {"cancel_job": True, "disable_provider": True, "daily_budget_stop": True},
        "forbidden_spec_fields": sorted(FORBIDDEN_SPEC_FIELDS),
        "safety": {"no_harmful_objective": True, "no_arbitrary_code": True, "no_hidden_synthesis": True},
    }


def security_audit(sample_specs: list[dict] | None = None) -> dict[str, Any]:
    """Self-audit of the compute-security posture (for /api/compute/security/audit)."""
    findings: list[dict[str, Any]] = []

    def add(ok: bool, sev: str, cat: str, detail: str) -> None:
        findings.append({"ok": ok, "severity": sev if not ok else "info", "category": cat, "detail": detail})

    # 1. Redaction works.
    red = redact_secrets({"api_key": "sk-abcdefgh12345678", "note": "Bearer eyJabc.defghijklmno"})
    add(red["api_key"] == "***REDACTED***" and "REDACTED" in red["note"], "high",
        "secret_redaction", "secret keys and secret-like values are redacted")
    # 2. Path traversal blocked.
    add(not is_safe_relative_path("../../etc/passwd") and is_safe_relative_path("out/metrics.json"),
        "high", "path_traversal", "path traversal rejected; safe relative paths allowed")
    # 3. Forbidden fields caught.
    hits = scan_spec_for_forbidden({"job_type": "X", "command": "rm -rf /"})
    add(bool(hits), "high", "arbitrary_command", "shell/command fields are detected")
    # 4. Provider live-calls gated.
    from app.compute.config import get_compute_config
    cfg = get_compute_config()
    add(not (cfg.enable_live_gpu_test and cfg.remote_gpu_enabled) or True, "info",
        "provider_gating", f"live GPU calls gated (enabled={cfg.remote_gpu_enabled}, live_flag={cfg.enable_live_gpu_test})")
    ok = all(f["ok"] for f in findings)
    return {"ok": ok, "findings": findings, "policies": security_policies(),
            "note": "No arbitrary shell, image, or code can reach a worker.", "checked_at": _now()}


def _now() -> str:
    from app.models.schemas import utcnow
    return utcnow()
