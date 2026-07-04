"""REINVENT4 bridge — status reporting only, never execution.

REINVENT4 is an external generative-chemistry tool. This module NEVER runs it
and NEVER fabricates its output. It only reports whether the tool is configured
so the loop can honestly label its provenance as ``CONFIGURED_BUT_NOT_RUN`` when
the binary/interpreter are not available.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings


def _configured() -> bool:
    settings = get_settings()
    return bool(getattr(settings, "reinvent4_bin", "")) and bool(
        getattr(settings, "reinvent4_python", "")
    )


def status() -> dict[str, Any]:
    """Report REINVENT4 availability without executing anything.

    Returns
    -------
    dict
        When configured: ``{"mode": "CONFIGURED", ...}`` (still not executed
        here). When not configured: ``{"mode": "CONFIGURED_BUT_NOT_RUN",
        "note": "REINVENT4 not installed; no fake output produced."}``.
    """
    if _configured():
        return {
            "mode": "CONFIGURED",
            "note": (
                "REINVENT4 paths are configured but this bridge does not execute "
                "the tool; run it via its own dedicated adapter."
            ),
            "executed": False,
        }
    return {
        "mode": "CONFIGURED_BUT_NOT_RUN",
        "note": "REINVENT4 not installed; no fake output produced.",
        "executed": False,
    }
