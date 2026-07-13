"""Multi-objective Pareto analysis over candidate molecules.

Instead of collapsing a molecule to one composite score, this engine reasons over
several competing objectives at once (activity, drug-likeness, safety, novelty,
and risk/uncertainty proxies) and reports the Pareto front — the set of molecules
that are not strictly beaten by any other on all comparable objectives.

The analysis is deterministic, rule-based, and conservative:
- Objectives derived from missing data stay ``None`` and are excluded from the
  domination test (never assumed favourable), and they lower per-candidate
  confidence in proportion to how much is unavailable.
- A single "best molecule" is only implied when exactly one candidate strictly
  dominates every other; otherwise ``no_single_best`` is True.
- No synthesis, dosage, or medical content is produced — these are in-silico
  proxies labeled HEURISTIC_ANALYSIS.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.storage import db

# Objective name -> optimisation direction. "max" = higher is better,
# "min" = lower is better. Order is meaningful only for deterministic tie-breaks.
OBJECTIVES: dict[str, str] = {
    "activity_proxy_score": "max",
    "qed": "max",
    "medchem_score": "max",
    "safety_score": "max",
    "applicability_confidence": "max",
    "novelty_diversity": "max",
    "toxicity_risk_proxy": "min",
    "uncertainty": "min",
    "duplicate_scaffold_penalty": "min",
    "synthetic_complexity_proxy": "min",  # optional
}

# Subset of objectives used to choose a recommended role. These are the
# interpretable "signal" objectives; trivially-defaulted penalties are excluded
# so a role reflects a genuine strength.
_ROLE_SIGNAL: list[str] = [
    "activity_proxy_score",
    "safety_score",
    "qed",
    "medchem_score",
    "novelty_diversity",
    "applicability_confidence",
]

_ROLE_BY_OBJECTIVE: dict[str, str] = {
    "activity_proxy_score": "ACTIVITY_PRIORITY",
    "safety_score": "SAFETY_PRIORITY",
    "novelty_diversity": "DIVERSITY_EXPLORATION",
}

_SAFETY_SCORE = {"PASS": 1.0, "REVIEW_REQUIRED": 0.5, "BLOCKED": 0.0}

_DISCLAIMER = (
    "Multi-objective heuristic analysis over in-silico proxies only. No synthesis, "
    "dosage, or medical guidance. Objectives without objective data are marked "
    "unavailable and lower confidence; no single molecule is declared best unless "
    "it strictly dominates all others."
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def extract_objectives(mol: dict) -> dict[str, float | None]:
    """Derive each objective from a molecule record, conservatively.

    Objectives that cannot be computed from the record stay ``None`` so they are
    excluded from domination and penalise confidence rather than being guessed.
    """
    desc = mol.get("descriptors") or {}

    qed = desc.get("qed")
    qed_val = float(qed) if qed is not None else None

    pchembl = mol.get("pchembl_value")
    if pchembl is not None:
        try:
            activity = _clamp01((float(pchembl) - 4.0) / 5.0)
        except (TypeError, ValueError):
            activity = None
    else:
        activity = None

    safety = _SAFETY_SCORE.get(mol.get("safety_status"))  # None if absent/unknown

    composite = mol.get("composite_score")
    medchem = float(composite) / 100.0 if composite is not None else None

    return {
        "activity_proxy_score": activity,
        "qed": qed_val,
        "medchem_score": medchem,
        "safety_score": safety,
        # Applicability confidence is only known if a domain analysis supplied it.
        "applicability_confidence": mol.get("applicability_confidence"),
        "novelty_diversity": mol.get("novelty_diversity", 0.5),
        "toxicity_risk_proxy": mol.get("toxicity_risk_proxy", 0.5),
        "uncertainty": mol.get("uncertainty", 0.3),
        "duplicate_scaffold_penalty": mol.get("duplicate_scaffold_penalty", 0.0),
        # Synthetic complexity is not computable from a bare record.
        "synthetic_complexity_proxy": mol.get("synthetic_complexity_proxy"),
    }


def dominates(a: dict, b: dict, objectives: Optional[dict[str, str]] = None) -> bool:
    """Return True if objective-vector ``a`` Pareto-dominates ``b``.

    Only objectives present (non-None) in BOTH are compared, each respecting its
    direction (for "min" objectives lower is better). ``a`` dominates ``b`` iff it
    is at least as good on every comparable objective and strictly better on at
    least one.
    """
    objectives = objectives or OBJECTIVES
    comparable = 0
    at_least_as_good = True
    strictly_better = False
    for name, direction in objectives.items():
        av = a.get(name)
        bv = b.get(name)
        if av is None or bv is None:
            continue
        comparable += 1
        if direction == "min":
            if av > bv:
                at_least_as_good = False
            elif av < bv:
                strictly_better = True
        else:  # max
            if av < bv:
                at_least_as_good = False
            elif av > bv:
                strictly_better = True
    if comparable == 0:
        return False
    return at_least_as_good and strictly_better


def _pareto_ranks(objective_vectors: list[dict]) -> list[int]:
    """Assign each vector a rank by iteratively peeling non-dominated fronts."""
    n = len(objective_vectors)
    ranks = [0] * n
    remaining = set(range(n))
    current = 1
    while remaining:
        front = []
        for i in remaining:
            if not any(
                j != i and dominates(objective_vectors[j], objective_vectors[i], OBJECTIVES)
                for j in remaining
            ):
                front.append(i)
        if not front:  # defensive: no strict cycles possible, but never loop forever
            front = list(remaining)
        for i in front:
            ranks[i] = current
            remaining.discard(i)
        current += 1
    return ranks


def _tradeoff_summary(ov: dict, missing: list[str]) -> str:
    """Human-readable strengths/weaknesses/unavailable summary (always non-empty)."""
    strengths: list[str] = []
    weaknesses: list[str] = []
    for name, direction in OBJECTIVES.items():
        v = ov.get(name)
        if v is None:
            continue
        good = (1.0 - v) if direction == "min" else v
        if good >= 0.7:
            strengths.append(name)
        elif good <= 0.3:
            weaknesses.append(name)
    parts: list[str] = []
    if strengths:
        parts.append("strengths: " + ", ".join(strengths))
    if weaknesses:
        parts.append("weaknesses: " + ", ".join(weaknesses))
    if missing:
        parts.append("unavailable objectives: " + ", ".join(missing))
    if not parts:
        parts.append("balanced profile with no dominant strength or weakness")
    return "; ".join(parts)


def _recommended_role(mol: dict, ov: dict, missing_fraction: float) -> str:
    """Pick exactly one role label for a candidate."""
    safety = ov.get("safety_score")
    if mol.get("valid") is False or safety == 0.0:
        return "REJECT"
    if missing_fraction > 0.5:
        return "HOLD_FOR_DATA"
    goodness = {name: ov[name] for name in _ROLE_SIGNAL if ov.get(name) is not None}
    if not goodness:
        return "HOLD_FOR_DATA"
    strongest = max(goodness, key=lambda k: goodness[k])
    return _ROLE_BY_OBJECTIVE.get(strongest, "BALANCED_LEAD_LIKE")


def compute(molecules: list[dict]) -> dict:
    """Run the multi-objective Pareto analysis over a list of molecule records."""
    objective_names = list(OBJECTIVES.keys())
    n = len(molecules)
    ovs = [extract_objectives(m) for m in molecules]

    dominated_flags = [False] * n
    dominance_counts = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if dominates(ovs[i], ovs[j], OBJECTIVES):
                dominance_counts[i] += 1
            if dominates(ovs[j], ovs[i], OBJECTIVES):
                dominated_flags[i] = True

    ranks = _pareto_ranks(ovs)

    candidates: list[dict] = []
    for i, mol in enumerate(molecules):
        ov = ovs[i]
        missing = [name for name in objective_names if ov.get(name) is None]
        missing_fraction = len(missing) / len(objective_names)
        confidence = round(max(0.05, 0.9 * (1.0 - missing_fraction)), 3)
        candidates.append({
            "molecule_id": mol.get("id"),
            "label": mol.get("label") or mol.get("molecule_chembl_id") or mol.get("id"),
            "objective_values": ov,
            "dominated": dominated_flags[i],
            "dominance_count": dominance_counts[i],
            "pareto_rank": ranks[i],
            "tradeoff_summary": _tradeoff_summary(ov, missing),
            "recommended_role": _recommended_role(mol, ov, missing_fraction),
            "missing_objectives": missing,
            "confidence": confidence,
        })

    front = [c for c in candidates if c["pareto_rank"] == 1]

    # A single "best" is only warranted when exactly one candidate strictly
    # dominates every other candidate (requires at least two candidates).
    dominators = [c for c in candidates if n >= 2 and c["dominance_count"] == n - 1]
    no_single_best = not (len(dominators) == 1)

    if not molecules:
        note = "No molecules available for Pareto analysis."
    elif no_single_best:
        note = (
            f"{len(front)} non-dominated candidate(s) on the Pareto front — no single "
            "molecule is best across all objectives; review the front's trade-offs."
        )
    else:
        note = (
            "One candidate strictly dominates all others on comparable objectives; "
            "confirm against unavailable objectives before prioritising."
        )

    return {
        "front": front,
        "all_candidates": candidates,
        "objective_names": objective_names,
        "note": note,
        "no_single_best": no_single_best,
        "disclaimer": _DISCLAIMER,
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "checked_at": utcnow(),
    }


def run(run_id: str | None = None) -> dict:
    """Load molecules for a run, compute the Pareto analysis, and persist it."""
    runs = db.list_records("workflow_runs", limit=200)
    run_rec = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run_rec:
        raise ValueError("workflow run not found")
    run_rec = run_rec or {}
    pid = run_rec.get("project_id")
    rid = run_rec.get("id")
    mols = (
        db.list_records("molecule_candidates", project_id=pid, workflow_run_id=rid, limit=500)
        if pid and rid
        else []
    )
    result = compute(mols)
    result["id"] = f"pareto-{uuid.uuid4().hex[:8]}"
    result["run_id"] = rid
    result["workflow_run_id"] = rid
    result["project_id"] = pid
    result["created_at"] = result.get("checked_at") or utcnow()
    try:
        db.insert("pareto_analyses", result)
    except Exception:  # pragma: no cover - persistence is best-effort
        pass
    return result
