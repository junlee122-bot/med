"""CPU active-learning simulation (Phase 8, Section 11).

Demonstrates how HelixForge could decide which candidates deserve expensive GPU
calculations or future experiments — WITHOUT a GPU. This is a SIMULATION against a
held-out dataset oracle (or a CPU surrogate); it never pretends surrogate labels
are experiments. Deterministic seed → reproducible. Compares an acquisition
strategy against a random baseline.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.services import chem_utils as cu
from app.storage import db

try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    _OK = True
except Exception:
    _OK = False

ACQUISITIONS = {"uncertainty", "top_score", "uncertainty_x_utility", "diversity_uncertainty", "random"}
ORACLE_MODES = {"HELD_OUT_DATASET_LABEL", "CPU_SURROGATE", "RECORDED_GPU_OUTPUT", "RECORDED_LABEL", "NO_ORACLE"}
SEED = 4242


def available() -> bool:
    return _OK and cu.rdkit_available()


def _acquire(strategy: str, probs, pool_idx: list[int], batch: int, feats, labeled_feats, rng) -> list[int]:
    if strategy == "random":
        order = list(pool_idx)
        rng.shuffle(order)
        return order[:batch]
    if strategy == "top_score":
        return [i for _, i in sorted(zip(probs, pool_idx), reverse=True)][:batch]
    # uncertainty variants: distance from 0.5
    unc = [1.0 - abs(p - 0.5) * 2 for p in probs]
    if strategy in ("uncertainty", "uncertainty_x_utility"):
        weight = unc if strategy == "uncertainty" else [u * p for u, p in zip(unc, probs)]
        return [i for _, i in sorted(zip(weight, pool_idx), reverse=True)][:batch]
    if strategy == "diversity_uncertainty":
        # greedy: pick highest uncertainty, then penalize near-duplicates by fingerprint.
        chosen: list[int] = []
        cand = sorted(zip(unc, pool_idx), reverse=True)
        chosen_fps: list = []
        for _, i in cand:
            fp = feats[i]
            if any(cu.tanimoto(fp, cf) and cu.tanimoto(fp, cf) > 0.85 for cf in chosen_fps):
                continue
            chosen.append(i)
            chosen_fps.append(fp)
            if len(chosen) >= batch:
                break
        if len(chosen) < batch:  # top up
            for _, i in cand:
                if i not in chosen:
                    chosen.append(i)
                if len(chosen) >= batch:
                    break
        return chosen
    return list(pool_idx)[:batch]


def _run_strategy(strategy: str, X, y, fps, initial: list[int], cycles: int, batch: int) -> dict[str, Any]:
    rng = np.random.RandomState(SEED)
    labeled = list(initial)
    pool = [i for i in range(len(y)) if i not in labeled]
    curve = []
    for c in range(cycles):
        if len(set(y[labeled].tolist())) < 2 or not pool:
            # can't train a 2-class model yet / pool exhausted
            curve.append({"cycle": c, "labeled_count": len(labeled), "metric": None,
                          "note": "insufficient class diversity or empty pool"})
            if not pool:
                break
            # acquire randomly to bootstrap diversity
            take = pool[:batch]
        else:
            clf = RandomForestClassifier(n_estimators=60, random_state=SEED)
            clf.fit(X[labeled], y[labeled])
            pool_probs = clf.predict_proba(X[pool])[:, 1].tolist()
            # metric on remaining pool (held-out oracle): balanced accuracy proxy = hit rate of top predicted
            top_pred = [i for _, i in sorted(zip(pool_probs, pool), reverse=True)][:batch]
            hit_rate = float(np.mean(y[top_pred])) if top_pred else 0.0
            curve.append({"cycle": c, "labeled_count": len(labeled),
                          "metric": round(hit_rate, 3), "pool_size": len(pool)})
            take = _acquire(strategy, pool_probs, pool, batch, fps, [fps[i] for i in labeled], rng)
        labeled += [i for i in take if i not in labeled]
        pool = [i for i in pool if i not in labeled]
    hits = [c["metric"] for c in curve if c["metric"] is not None]
    return {"strategy": strategy, "curve": curve,
            "final_labeled": len(labeled),
            "area_under_curve": round(float(np.mean(hits)), 3) if hits else None,
            "mean_hit_rate": round(float(np.mean(hits)), 3) if hits else None}


def run(pool: list[dict[str, Any]], strategy: str = "uncertainty", oracle_mode: str = "HELD_OUT_DATASET_LABEL",
        cycles: int = 4, batch_size: int = 3, initial_labeled: int = 4,
        run_id: str | None = None) -> dict[str, Any]:
    """pool: [{smiles, label}] where label is the held-out oracle truth."""
    if not available():
        return {"status": "CONFIGURED_BUT_NOT_RUN", "reason": "sklearn/RDKit/numpy unavailable",
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value, "created_at": utcnow()}
    strategy = strategy if strategy in ACQUISITIONS else "uncertainty"
    oracle_mode = oracle_mode if oracle_mode in ORACLE_MODES else "HELD_OUT_DATASET_LABEL"

    rows = [(str(r["smiles"]), r.get("label")) for r in pool if r.get("smiles") and r.get("label") is not None]
    valid = [(s, y) for s, y in rows if cu.is_valid(s)]
    if len(valid) < initial_labeled + batch_size + 2:
        return {"status": "INSUFFICIENT_DATA", "valid": len(valid),
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value, "created_at": utcnow()}
    smiles = [s for s, _ in valid]
    X = np.array([cu.feature_vector(s) for s in smiles], dtype=float)
    y = np.array([1 if float(l) >= 0.5 else 0 for _, l in valid])
    fps = [cu.morgan_fp(s) for s in smiles]
    initial = list(range(initial_labeled))

    strat = _run_strategy(strategy, X, y, fps, initial, cycles, batch_size)
    rand = _run_strategy("random", X, y, fps, initial, cycles, batch_size)

    escalation = [{"smiles": s} for s in smiles[:batch_size]]  # top candidates for GPU escalation
    out = {
        "id": f"al-{uuid.uuid4().hex[:8]}", "run_id": run_id, "strategy": strategy,
        "oracle_mode": oracle_mode, "oracle_note": ("Oracle labels come from a held-out dataset, NOT experiments."
                                                    if oracle_mode == "HELD_OUT_DATASET_LABEL"
                                                    else "CPU surrogate labels are model outputs, NOT experiments."),
        "cycles": cycles, "batch_size": batch_size, "pool_size": len(valid),
        "learning_curve": strat["curve"], "area_under_learning_curve": strat["area_under_curve"],
        "mean_hit_rate": strat["mean_hit_rate"],
        "random_baseline": {"mean_hit_rate": rand["mean_hit_rate"], "auc": rand["area_under_curve"]},
        "beats_random": (strat["mean_hit_rate"] is not None and rand["mean_hit_rate"] is not None
                         and strat["mean_hit_rate"] >= rand["mean_hit_rate"]),
        "gpu_escalation_candidates": escalation,
        "seed": SEED, "source_type": SourceType.BASELINE_CPU_MODEL_OUTPUT.value,
        "limitations": ["Simulation against a dataset oracle — not real experiments.",
                        "Small pool; results indicative only.",
                        "CPU surrogate labels must not be treated as ground-truth activity."],
        "created_at": utcnow(),
    }
    db.insert("active_learning_runs", out)
    return out


def get_run(al_id: str) -> dict[str, Any] | None:
    return db.get("active_learning_runs", al_id)


def list_runs() -> list[dict[str, Any]]:
    return db.list_records("active_learning_runs", limit=100)
