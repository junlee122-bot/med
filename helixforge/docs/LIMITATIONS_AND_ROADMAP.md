# Limitations & Roadmap

## Honest status of every capability

| Capability | Status |
|---|---|
| PubMed / ChEMBL / ClinicalTrials.gov search | **Implemented with real tool** (live HTTP) |
| RDKit validation / descriptors / similarity | **Implemented with real tool** (local) |
| TDC / PyTDC dataset loading | **Implemented with real tool** (downloads on first use) — used as evaluation/training **substrate**, not a fitted per-candidate predictor |
| AutoDock Vina docking | **Implemented as fixture-based job runner** — fixture only; arbitrary receptor preparation is **Planned** |
| REINVENT4 generation | **Implemented as config/job runner** — real TOML config; a run needs an external REINVENT4 install; RL training is out of scope |
| Multi-agent runtime + critic loop | **Implemented** (deterministic; optional LLM adapter Planned) |
| Transparent scoring | **Implemented** |
| Safety gate + report lint | **Implemented** |
| Clinical/regulatory checklist | **Implemented as heuristic** (ASSUMPTION labels); guidance-document RAG is **Planned** (FUTURE_RAG_ADAPTER) |
| Korean + English reports, JSON/export bundle | **Implemented** |
| Business-value model | **Implemented** (illustrative ranges, not field-validated) |

## What this system does NOT do

- No wet-lab validation, clinical efficacy, or regulatory approval is claimed.
- No synthesis routes, reagents, reaction conditions, purification, dosage, or
  medical advice are produced — by policy.
- ADMET/docking numbers are in-silico estimates or dataset metadata, not
  experimental measurements.
- The clinical/regulatory output is high-level planning, not advice.

## Roadmap

1. **Real generative loop** — wire a REINVENT4 runtime; parse + RDKit-validate
   generated SMILES; score and rank as `REAL_TOOL_OUTPUT`.
2. **Trained ADMET predictors** — train ChemProp/graph models on the TDC splits
   already loaded; report ROC-AUC/RMSE on held-out test; label
   `BASELINE_MODEL_OUTPUT`.
3. **Docking beyond fixtures** — receptor preparation pipeline (protonation,
   grid box, PDBQT) behind the existing job interface.
4. **Guidance RAG** — vector DB over FDA/MFDS guidance; replace heuristic
   checklist with retrieved, source-cited items.
5. **LLM orchestration adapter** — optional; default remains deterministic and
   key-free.
6. **Resource router** — distill simple routing to a smaller model; measure real
   cost reduction.
7. **Scale-out** — Postgres swap (storage layer is already narrow), task queue
   for long Vina/REINVENT jobs.
