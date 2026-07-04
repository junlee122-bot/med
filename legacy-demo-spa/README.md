# ⚠️ Archived — early mock SPA (NOT the competition submission)

This folder contains an **early, front-end-only mock demo** built at the very
start of the project. It uses simulated/seeded data and does **not** connect to
real scientific tools.

## The official competition system is [`../helixforge/`](../helixforge/)

`helixforge/` is the real, integration-first monorepo:
- **Backend** (FastAPI) with live PubMed / ChEMBL / ClinicalTrials.gov, local
  RDKit / TDC, honest configured-not-run Vina / REINVENT4, a 17-agent runtime,
  record/replay, evaluation, safety/evidence linting, and Korean reports.
- **Frontend** (Vite/React/TS) wired to that backend.

Judges and reviewers should ignore this archived SPA and use `helixforge/`.
This folder is kept only for project history; it is not maintained.
