# Safe Molecule Optimization Loop

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Package:** `app/services/optimization_loop/` · **Endpoints:** `/api/optimization-loop/{run,run/{id},run/{id}/trace,run/{id}/report}`

**What it is.** An in-silico optimization loop over candidate molecules. Two safe modes: **SELECTION_LOOP** (re-rank the existing candidate pool under perturbed scoring weights — "optimization by selection", no new structures) and **LOCAL_HEURISTIC_GENERATION** (conservative RDKit-validated analog suggestions from a small safe fragment set). REINVENT4 is used only if actually installed; otherwise it stays `CONFIGURED_BUT_NOT_RUN` and is **never faked**.

**Loop.** Seed → score → select → generate/resample → validate (reject invalid) → safety gate (reject blocked) → re-score → Pareto rank → compare generations.

**Objective.** activity proxy, QED, Lipinski, medchem, applicability domain, safety, novelty/diversity, minus uncertainty / duplicate-scaffold penalties.

**Limitations.** In-silico candidate prioritization, **not synthesis or experimental validation**. **No synthesis routes, reaction conditions, reagents, or dosing** are produced anywhere. Generated structures are computational suggestions for expert review; invalid or safety-blocked candidates are rejected and counted. Local heuristic generation is clearly labeled `LOCAL_HEURISTIC_GENERATED`.
