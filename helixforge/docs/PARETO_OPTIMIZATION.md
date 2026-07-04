# Multi-Objective Optimization and Pareto Analysis

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `pareto_optimization.py` · **Endpoints:** `/api/optimization/pareto/run`

**Objectives.** maximize activity proxy, QED, medchem, safety, applicability confidence, novelty/diversity; minimize toxicity-risk proxy, uncertainty, duplicate/scaffold penalty, synthetic-complexity proxy. Missing objectives stay None.

**Analysis.** Standard Pareto domination over shared objectives (respecting direction); non-dominated fronts peeled into ranks; per-candidate trade-off summary and recommended role (BALANCED_LEAD_LIKE / ACTIVITY_PRIORITY / SAFETY_PRIORITY / DIVERSITY_EXPLORATION / HOLD_FOR_DATA / REJECT).

**Honesty.** Missing objectives lower confidence. No single "best" molecule unless one strictly dominates all others (`no_single_best`). Trade-offs are shown, not hidden behind one number.
