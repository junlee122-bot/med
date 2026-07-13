"""CPU-first QSAR / ADMET baseline models (Phase 8, Section 9).

Honest scikit-learn baselines on RDKit features with scaffold-split validation,
duplicate-leakage detection, bootstrap uncertainty, and applicability domain.
scikit-learn is OPTIONAL: absent → CONFIGURED_BUT_NOT_RUN (no fabricated metrics).
A baseline is never called a validated clinical model. Prediction requires a
trained model held in-process; if the model artifact is missing, prediction is
blocked (honest) rather than fabricated. No model binary is committed.
"""
from __future__ import annotations

import hashlib
import math
import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.services import chem_utils as cu
from app.storage import db

try:
    import numpy as np
    _NP = True
except Exception:
    _NP = False

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.metrics import (
        balanced_accuracy_score, brier_score_loss, mean_absolute_error,
        mean_squared_error, r2_score, roc_auc_score,
    )
    _SK = True
except Exception:
    _SK = False

# In-process model cache (model_id -> fitted estimator + training fps). Not persisted
# as a binary; a process restart clears it and prediction reports the artifact missing.
_MODEL_CACHE: dict[str, dict[str, Any]] = {}
SEED = 1234


def available() -> dict[str, Any]:
    return {"sklearn": _SK, "numpy": _NP, "rdkit": cu.rdkit_available(),
            "status": "AVAILABLE" if (_SK and _NP and cu.rdkit_available()) else "CONFIGURED_BUT_NOT_RUN"}


def _scaffold_split(smiles: list[str], test_frac: float = 0.3) -> tuple[list[int], list[int]]:
    """Group by Bemis-Murcko scaffold; whole scaffolds go to one side (no leakage)."""
    groups: dict[str, list[int]] = {}
    for i, s in enumerate(smiles):
        scaf = cu.murcko_scaffold(s) or f"__none_{i}"
        groups.setdefault(scaf, []).append(i)
    ordered = sorted(groups.values(), key=len, reverse=True)
    n_test_target = int(len(smiles) * test_frac)
    test: list[int] = []
    train: list[int] = []
    for grp in ordered:
        if len(test) < n_test_target:
            test.extend(grp)
        else:
            train.extend(grp)
    return sorted(train), sorted(test)


def _duplicate_leakage(smiles: list[str], train_idx: list[int], test_idx: list[int]) -> int:
    tr = {cu.canonical_smiles(smiles[i]) for i in train_idx}
    te = {cu.canonical_smiles(smiles[i]) for i in test_idx}
    return len(tr & te - {None})


def _class_metrics(y_true, y_prob) -> dict[str, Any]:
    y_pred = [1 if p >= 0.5 else 0 for p in y_prob]
    out: dict[str, Any] = {}
    try:
        if len(set(y_true)) > 1:
            out["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 3)
        out["balanced_accuracy"] = round(float(balanced_accuracy_score(y_true, y_pred)), 3)
        out["brier"] = round(float(brier_score_loss(y_true, y_prob)), 3)
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        out["sensitivity"] = round(tp / (tp + fn), 3) if (tp + fn) else None
        out["specificity"] = round(tn / (tn + fp), 3) if (tn + fp) else None
        out["confusion_matrix"] = {"tp": tp, "tn": tn, "fp": fp, "fn": fn}
    except Exception as e:
        out["error"] = str(e)[:120]
    return out


def _reg_metrics(y_true, y_pred) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        out["rmse"] = round(math.sqrt(mean_squared_error(y_true, y_pred)), 4)
        out["mae"] = round(float(mean_absolute_error(y_true, y_pred)), 4)
        out["r2"] = round(float(r2_score(y_true, y_pred)), 4)
        try:
            from scipy.stats import spearmanr
            rho = spearmanr(y_true, y_pred).correlation
            out["spearman"] = round(float(rho), 4) if rho == rho else None
        except Exception:
            out["spearman"] = None
    except Exception as e:
        out["error"] = str(e)[:120]
    return out


def train(dataset: list[dict[str, Any]], task: str = "classification",
          endpoint: str = "activity", model_family: str = "random_forest",
          run_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    """dataset: [{smiles, label}]. task: classification|regression."""
    avail = available()
    if avail["status"] != "AVAILABLE":
        return {"status": "CONFIGURED_BUT_NOT_RUN", "reason": "scikit-learn/RDKit/numpy unavailable",
                "available": avail, "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value, "created_at": utcnow()}

    rows = [(str(r["smiles"]), r.get("label")) for r in dataset
            if r.get("smiles") and r.get("label") is not None]
    valid_rows = [(s, y) for s, y in rows if cu.is_valid(s)]
    invalid_count = len(rows) - len(valid_rows)
    if len(valid_rows) < 8:
        return {"status": "INSUFFICIENT_DATA", "reason": f"only {len(valid_rows)} valid rows (<8)",
                "valid_rows": len(valid_rows), "invalid_count": invalid_count,
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value, "created_at": utcnow()}

    smiles = [s for s, _ in valid_rows]
    feats = [cu.feature_vector(s) for s in smiles]
    labels = [y for _, y in valid_rows]
    X = np.array(feats, dtype=float)
    y = np.array(labels, dtype=float)

    train_idx, test_idx = _scaffold_split(smiles)
    if not test_idx or not train_idx:
        return {"status": "INSUFFICIENT_DATA", "reason": "scaffold split produced an empty side",
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value, "created_at": utcnow()}
    leakage = _duplicate_leakage(smiles, train_idx, test_idx)

    Xtr, Xte = X[train_idx], X[test_idx]
    ytr, yte = y[train_idx], y[test_idx]

    if task == "classification":
        est = (RandomForestClassifier(n_estimators=100, random_state=SEED)
               if model_family == "random_forest" else LogisticRegression(max_iter=500))
        est.fit(Xtr, (ytr >= 0.5).astype(int))
        prob = est.predict_proba(Xte)[:, 1] if hasattr(est, "predict_proba") else est.predict(Xte)
        metrics = _class_metrics((yte >= 0.5).astype(int).tolist(), [float(p) for p in prob])
        class_balance = {"positives": int((y >= 0.5).sum()), "negatives": int((y < 0.5).sum())}
    else:
        est = (RandomForestRegressor(n_estimators=100, random_state=SEED)
               if model_family == "random_forest" else Ridge())
        est.fit(Xtr, ytr)
        pred = est.predict(Xte)
        metrics = _reg_metrics(yte.tolist(), [float(p) for p in pred])
        class_balance = None

    # Bootstrap uncertainty: std of test predictions across resampled ensembles.
    uncertainty = _bootstrap_uncertainty(est, Xtr, ytr, Xte, task)

    model_id = f"cpumodel-{uuid.uuid4().hex[:8]}"
    checksum = hashlib.sha256(f"{model_id}{metrics}{SEED}".encode()).hexdigest()[:16]
    _MODEL_CACHE[model_id] = {"estimator": est, "train_smiles": [smiles[i] for i in train_idx], "task": task}

    small_sample = len(test_idx) < 20
    rec = {
        "id": model_id, "project_id": project_id, "run_id": run_id,
        "workflow_run_id": run_id, "model_family": model_family, "task": task,
        "endpoint": endpoint, "feature_method": "morgan_1024",
        "dataset_summary": {"total": len(rows), "valid": len(valid_rows), "invalid": invalid_count,
                            "train": len(train_idx), "test": len(test_idx), "class_balance": class_balance},
        "split_strategy": "scaffold_split", "duplicate_leakage_count": leakage,
        "metrics": metrics, "uncertainty": uncertainty,
        "applicability_method": "morgan_tanimoto_nearest_neighbor",
        "sample_size_warning": ("test set < 20 — metrics are indicative, not statistically powered."
                                if small_sample else None),
        "model_version": "1", "checksum": checksum,
        "validation_status": "VALIDATED_BASELINE" if leakage == 0 else "REVIEW_REQUIRED_LEAKAGE",
        "human_review_status": "PENDING",
        "source_type": SourceType.BASELINE_CPU_MODEL_OUTPUT.value,
        "package_versions": _pkg_versions(), "seed": SEED,
        "limitations": ["CPU baseline — NOT a validated clinical model; not production-grade.",
                        "Small dataset; scaffold split; verify before any decision.",
                        "Applicability domain limits reliable prediction range."],
        "created_at": utcnow(),
    }
    db.insert("cpu_models", rec)
    db.insert("model_checkpoints", {"id": f"ckpt-{model_id}",
                                    "project_id": project_id, "run_id": run_id,
                                    "workflow_run_id": run_id, "compute_job_id": None,
                                    "model_family": model_family, "task": task, "checkpoint_path": "(in-process)",
                                    "checksum": checksum, "metrics": metrics,
                                    "validation_status": rec["validation_status"],
                                    "source_type": SourceType.BASELINE_CPU_MODEL_OUTPUT.value,
                                    "created_at": utcnow()})
    return rec


def _bootstrap_uncertainty(est, Xtr, ytr, Xte, task: str, n: int = 8) -> dict[str, Any]:
    try:
        from sklearn.base import clone
        rng = np.random.RandomState(SEED)
        preds = []
        for _ in range(n):
            idx = rng.randint(0, len(Xtr), len(Xtr))
            m = clone(est)
            yb = (ytr >= 0.5).astype(int) if task == "classification" else ytr
            m.fit(Xtr[idx], yb[idx])
            p = (m.predict_proba(Xte)[:, 1] if task == "classification" and hasattr(m, "predict_proba")
                 else m.predict(Xte))
            preds.append(p)
        arr = np.array(preds)
        return {"method": "bootstrap_ensemble", "n_models": n,
                "mean_std": round(float(arr.std(axis=0).mean()), 4)}
    except Exception:
        return {"method": "unavailable", "note": "bootstrap uncertainty could not be computed"}


def _pkg_versions() -> dict[str, str]:
    out = {}
    for mod in ("sklearn", "numpy", "scipy", "rdkit"):
        try:
            from importlib.metadata import version
            out[mod] = version(mod)
        except Exception:
            out[mod] = "unknown"
    return out


def predict(model_id: str, smiles_list: list[str]) -> dict[str, Any]:
    rec = db.get("cpu_models", model_id)
    if not rec:
        return {"status": "MODEL_NOT_FOUND", "source_type": SourceType.TOOL_ERROR.value}
    cached = _MODEL_CACHE.get(model_id)
    if not cached:
        # Model metadata exists but the in-process artifact is gone — do NOT fabricate.
        return {"status": "MODEL_ARTIFACT_MISSING", "model_id": model_id,
                "reason": "Trained estimator not in process (restarted?). Retrain to predict.",
                "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value}
    est = cached["estimator"]
    train_smiles = cached["train_smiles"]
    preds = []
    from app.services import applicability_domain as ad
    for s in smiles_list:
        fv = cu.feature_vector(s)
        if fv is None:
            preds.append({"smiles": s, "valid": False, "prediction": None,
                          "applicability": "INVALID"})
            continue
        X = np.array([fv], dtype=float)
        if cached["task"] == "classification" and hasattr(est, "predict_proba"):
            val = float(est.predict_proba(X)[0, 1])
        else:
            val = float(est.predict(X)[0])
        dom = ad.assess_molecule(s, train_smiles)
        preds.append({"smiles": s, "valid": True, "prediction": round(val, 4),
                      "applicability": dom.get("domain_status", "UNKNOWN"),
                      "confidence_note": "Out-of-domain predictions are unreliable."
                      if dom.get("domain_status") == "OUT_OF_DOMAIN" else None})
    return {"status": "OK", "model_id": model_id, "task": cached["task"],
            "predictions": preds, "source_type": SourceType.BASELINE_CPU_MODEL_OUTPUT.value,
            "disclaimer": "CPU baseline prediction — not clinical/safety validation.", "checked_at": utcnow()}


def list_models(run_id: str | None = None,
                project_id: str | None = None) -> list[dict[str, Any]]:
    return db.list_records("cpu_models", project_id=project_id,
                           workflow_run_id=run_id, limit=200)


def get_model(model_id: str) -> dict[str, Any] | None:
    return db.get("cpu_models", model_id)
