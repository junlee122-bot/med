"""Safety gate for the optimization loop.

Every candidate that enters or is produced by the loop must clear this gate
before it can be scored or reported. The gate combines two conservative checks:

1. **Structural validity** — the SMILES must parse under RDKit. Invalid
   structures are rejected outright (never scored, never advanced).
2. **Content safety** — a *neutral, non-actionable* descriptor string is passed
   through :func:`app.services.safety_lint.lint_report`. If the linter returns a
   ``BLOCKED`` status the candidate is rejected.

The gate never emits or reasons about synthesis routes, reagents, reaction
conditions, dosing, or any procedural chemistry. It only decides pass / reject.
"""
from __future__ import annotations

from typing import Any

from app.services.safety_lint import lint_report

try:  # RDKit is an optional-but-expected local dependency.
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - environment without RDKit
    RDKIT = False


def _neutral_descriptor_text(smiles: str) -> str:
    """Build a neutral, non-actionable description used only for content linting.

    The string deliberately contains no procedural chemistry — just a statement
    that the structure is an in-silico suggestion queued for computational
    review. It exists so the content linter has something to inspect.
    """
    safe_smiles = "".join(ch for ch in (smiles or "") if ch.isprintable())
    return (
        "In-silico candidate structure queued for computational review only. "
        f"Canonical descriptor token: {safe_smiles}. "
        "No laboratory instructions, no dosing, and no procedural chemistry are attached."
    )


def screen(smiles: str, context: str = "") -> dict[str, Any]:
    """Screen a candidate SMILES for structural validity and content safety.

    Parameters
    ----------
    smiles:
        Candidate SMILES string to validate.
    context:
        Optional extra text folded into the neutral descriptor string before
        linting. Used so callers (and tests) can verify that genuinely blocked
        content is rejected. Defaults to empty.

    Returns
    -------
    dict
        ``{"ok": bool, "reason": str}``. ``ok`` is ``True`` only when the
        structure parses AND the content lint does not return ``BLOCKED``.
    """
    if not smiles or not str(smiles).strip():
        return {"ok": False, "reason": "empty_smiles"}

    if RDKIT:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"ok": False, "reason": "invalid_structure"}
        canonical = Chem.MolToSmiles(mol)
    else:
        # Without RDKit we cannot validate structure; do not fabricate a pass.
        return {"ok": False, "reason": "rdkit_unavailable"}

    text = _neutral_descriptor_text(canonical)
    if context:
        text = f"{text} {context}"
    report = lint_report(text, require_disclaimer=False)
    if report.get("status") == "BLOCKED":
        return {"ok": False, "reason": "safety_block"}
    return {"ok": True, "reason": "passed_validity_and_safety_lint"}
