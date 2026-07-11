"""Compute capability detection — safe, time-limited, install-free.

Detects CPU/memory/disk, optional scientific packages (RDKit, TDC, sklearn, torch,
numpy/scipy/pandas), local tool binaries (Vina, REINVENT4), and remote-GPU
readiness. A missing GPU is never an error. Local checks NEVER touch the network;
only `mode="remote"` may contact a configured provider. Deep checks (which could
be slower) are opt-in via `mode="deep"`.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import subprocess
from typing import Any

from app.compute.config import get_compute_config
from app.compute.schemas import ComputeProfile
from app.models.schemas import utcnow


def _pkg_version(mod_name: str) -> tuple[bool, str | None]:
    """Is a package importable? Returns (available, version-or-None) WITHOUT importing
    heavy modules where a spec check suffices."""
    try:
        spec = importlib.util.find_spec(mod_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        return False, None
    if spec is None:
        return False, None
    version = None
    try:
        from importlib.metadata import version as _v
        version = _v(mod_name)
    except Exception:
        version = None
    return True, version


def _cpu_info() -> dict[str, Any]:
    logical = os.cpu_count() or 1
    mem_gb = None
    try:  # best-effort; never required
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        mem_gb = round(page * pages / (1024 ** 3), 1)
    except (ValueError, OSError, AttributeError):
        mem_gb = None
    disk_free_gb = None
    try:
        disk_free_gb = round(shutil.disk_usage(os.getcwd()).free / (1024 ** 3), 1)
    except OSError:
        disk_free_gb = None
    return {
        "available": True,
        "logical_cores": logical,
        "memory_gb_estimate": mem_gb,
        "disk_free_gb_estimate": disk_free_gb,
        "process_pool_supported": logical > 1,
    }


def _torch_cuda(deep: bool) -> dict[str, Any]:
    """CUDA check. Safe: torch.cuda.is_available() does not require a GPU and
    returns False cleanly on CPU-only machines. Only run the import in deep mode
    (importing torch can be slow); otherwise report availability by spec only."""
    available, ver = _pkg_version("torch")
    out: dict[str, Any] = {"available": available, "version": ver,
                           "cuda_available": False, "cuda_device_count": 0, "deep_check_run": False}
    if available and deep:
        try:
            torch = importlib.import_module("torch")
            out["cuda_available"] = bool(torch.cuda.is_available())
            out["cuda_device_count"] = int(torch.cuda.device_count()) if out["cuda_available"] else 0
            out["deep_check_run"] = True
        except Exception:
            out["cuda_available"] = False
    return out


def _nvidia_smi(deep: bool, timeout: int) -> dict[str, Any]:
    """Optional, time-limited nvidia-smi presence check. Never required."""
    path = shutil.which("nvidia-smi")
    out: dict[str, Any] = {"present": bool(path), "probed": False, "gpu_count": 0}
    if path and deep:
        try:
            res = subprocess.run([path, "--query-gpu=name", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=timeout)
            out["probed"] = True
            if res.returncode == 0:
                out["gpu_count"] = len([l for l in res.stdout.splitlines() if l.strip()])
        except (subprocess.TimeoutExpired, OSError):
            out["probed"] = True
    return out


def _local_tools(deep: bool) -> dict[str, Any]:
    from app.config import get_settings
    s = get_settings()
    rdkit_ok, rdkit_ver = _pkg_version("rdkit")
    tdc_ok, tdc_ver = _pkg_version("tdc") if _pkg_version("tdc")[0] else _pkg_version("pytdc")
    sk_ok, sk_ver = _pkg_version("sklearn")
    np_ok, _ = _pkg_version("numpy")
    scipy_ok, _ = _pkg_version("scipy")
    pd_ok, _ = _pkg_version("pandas")
    vina_bin = s.vina_bin or "vina"
    vina_present = bool(shutil.which(vina_bin)) or _pkg_version("vina")[0]
    reinvent_present = bool(s.reinvent4_bin) or bool(s.reinvent4_python)
    return {
        "rdkit": {"available": rdkit_ok, "version": rdkit_ver},
        "tdc": {"available": tdc_ok, "version": tdc_ver, "deep_check_run": False},
        "sklearn": {"available": sk_ok, "version": sk_ver},
        "numpy": {"available": np_ok}, "scipy": {"available": scipy_ok}, "pandas": {"available": pd_ok},
        "vina": {"available": vina_present,
                 "status": "AVAILABLE" if vina_present else "CONFIGURED_NOT_RUN"},
        "reinvent4": {"available": reinvent_present,
                      "status": "AVAILABLE" if reinvent_present else "CONFIGURED_NOT_RUN"},
        "docker": {"available": bool(shutil.which("docker"))},
    }


def _recorded_gpu_artifacts() -> dict[str, Any]:
    """Count recorded GPU outputs available for replay (no network)."""
    try:
        from app.storage import db
        arts = [a for a in db.list_records("compute_artifacts", limit=500)
                if a.get("source_type") == "RECORDED_GPU_OUTPUT"
                or (a.get("metadata") or {}).get("recorded_gpu")]
        return {"available": bool(arts), "count": len(arts)}
    except Exception:
        return {"available": False, "count": 0}


def detect(mode: str = "local") -> dict[str, Any]:
    """mode: local (no network, no heavy imports) | deep (imports + nvidia-smi) |
    remote (also probes a configured provider health, time-limited)."""
    mode = mode if mode in ("local", "deep", "remote") else "local"
    deep = mode in ("deep", "remote")
    cfg = get_compute_config()
    warnings: list[str] = []

    cpu = _cpu_info()
    torch = _torch_cuda(deep)
    nvsmi = _nvidia_smi(deep, cfg.probe_timeout_seconds)
    local_tools = _local_tools(deep)
    recorded = _recorded_gpu_artifacts()

    remote: dict[str, Any] = {
        "configured": cfg.remote_configured(), "enabled": cfg.remote_gpu_enabled,
        "provider": cfg.remote_gpu_provider if cfg.remote_configured() else None,
        "live_probe_run": False, "healthy": None, "detail": None,
    }
    if mode == "remote" and cfg.remote_configured() and cfg.remote_gpu_enabled:
        try:
            from app.compute.provider_registry import get_provider
            prov = get_provider()
            health = prov.health_check(live=True)
            remote.update({"live_probe_run": True, "healthy": health.get("healthy"),
                           "detail": health.get("detail")})
        except Exception as e:  # never crash on a provider issue
            remote.update({"live_probe_run": True, "healthy": False, "detail": str(e)[:160]})
    elif mode == "remote" and not cfg.remote_configured():
        warnings.append("Remote mode requested but no provider is configured.")

    gpu_present = bool(torch.get("cuda_available")) or nvsmi.get("gpu_count", 0) > 0
    if cfg.remote_gpu_enabled and cfg.remote_configured():
        profile = ComputeProfile.REMOTE_GPU_ENABLED
    elif cfg.remote_configured():
        profile = ComputeProfile.REMOTE_GPU_READY
    elif recorded["available"]:
        profile = ComputeProfile.RECORDED_GPU_REPLAY
    elif not local_tools["rdkit"]["available"]:
        profile = ComputeProfile.COMPUTE_DEGRADED
        warnings.append("RDKit unavailable — core cheminformatics is degraded.")
    elif any(local_tools[t]["available"] for t in ("tdc", "sklearn")):
        profile = ComputeProfile.CPU_WITH_OPTIONAL_LOCAL_TOOLS
    else:
        profile = ComputeProfile.CPU_ONLY

    if not local_tools["sklearn"]["available"]:
        warnings.append("scikit-learn absent — CPU QSAR baselines degrade to configured-not-run.")

    recommended = ("REMOTE_GPU" if profile == ComputeProfile.REMOTE_GPU_ENABLED
                   else "RECORDED_GPU_REPLAY" if profile == ComputeProfile.RECORDED_GPU_REPLAY
                   else "CPU_ONLY")

    return {
        "profile": profile, "cpu": cpu, "local_tools": local_tools,
        "gpu_present_locally": gpu_present, "torch": torch, "nvidia_smi": nvsmi,
        "remote_gpu": remote, "recorded_gpu_artifacts": recorded,
        "recommended_mode": recommended, "mode": mode, "deep_check_run": deep,
        "warnings": warnings, "checked_at": utcnow(),
        "note": ("CPU-only is a complete scientific mode. GPU is an optional accelerator; "
                 "missing GPU is not an error."),
    }
