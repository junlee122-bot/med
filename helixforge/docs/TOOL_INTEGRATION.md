# Tool Integration Guide

Each tool is an adapter under `backend/app/adapters/`. This guide covers what is
real out of the box, how to enable the optional tools, and the exact endpoints.

## Live public APIs (real with zero setup)

### PubMed — `PubMedAdapter` (`pubmed.py`)
- **API:** NCBI E-utilities (`esearch` → `efetch`/`esummary`).
- **Endpoint:** `POST /api/pubmed/search` `{query, max_results}`.
- **Auth:** none required. Set `NCBI_API_KEY` (rate limit 3→10 req/s) and
  `NCBI_EMAIL` (NCBI usage policy). Retry + timeout applied.
- **Returns:** PMID, title, abstract, journal, year, authors, url, retrieved_at.

### ClinicalTrials.gov — `ClinicalTrialsGovAdapter` (`clinicaltrials.py`)
- **API:** ClinicalTrials.gov **v2** REST.
- **Endpoint:** `POST /api/clinicaltrials/search` `{condition, query, max_results}`.
- **Returns:** NCT id, brief title, status, phase, conditions, interventions,
  primary outcomes, url. Pagination handled up to `max_results`.

### ChEMBL — `ChEMBLAdapter` (`chembl.py`)
- **API:** ChEMBL web services.
- **Endpoints:** `POST /api/chembl/search-targets`, `/search-molecules`,
  `/activities` (`{target_chembl_id, activity_type, max_results}`).
- **Returns:** ChEMBL ids, preferred names, organism, structures (SMILES),
  activities (IC50/pChEMBL). Pagination handled.

## Local scientific tools (real once installed)

### RDKit — `RDKitAdapter` (`rdkit_adapter.py`)
- **Install:** `pip install rdkit` (wheel) or conda (`environment.yml`).
- **Endpoints:** `POST /api/rdkit/validate`, `/descriptors`, `/similarity`.
- **Returns:** validity, canonical SMILES, MW, logP, HBD/HBA, TPSA, rotatable
  bonds, ring count, QED, Lipinski pass/violations, Morgan-fingerprint
  Tanimoto similarity. Invalid SMILES return a clear `TOOL_ERROR`-style
  validation failure (not a crash).

### TDC / PyTDC — `TDCAdapter` (`tdc_adapter.py`)
- **Install:** `pip install PyTDC`. Datasets download on first use.
- **Endpoints:** `GET /api/tdc/datasets`, `POST /api/tdc/load`,
  `/benchmark-summary`.
- **Datasets:** Caco2_Wang, Lipophilicity_AstraZeneca, Solubility_AqSolDB,
  hERG, Ames, DILI.
- **Returns:** dataset name, task, row count, columns, split summary
  (train/valid/test), preview rows. Metadata is real; it grounds an honest
  ADMET benchmark (train a predictor on the train split, report on the test
  split — no fabricated metrics).

## Optional external tools (honest degradation)

These report `CONFIGURED_BUT_NOT_RUN` (or `TOOL_ERROR`) until configured — never
a fabricated result.

### AutoDock Vina — `VinaAdapter` (`vina_adapter.py`)
- **Enable:** install Vina (`pip install vina` or the AutoDock binary) and set
  `VINA_BIN` (Settings or `.env`).
- **Endpoints:** `POST /api/vina/fixture-dock`, `/score`, `GET /api/vina/jobs/{id}`.
- **Fixtures:** `backend/fixtures/vina/` (sample ligand/receptor). Docking is
  **fixture-based**; arbitrary receptor preparation (grid box, protonation,
  PDBQT conversion) is future work and requires expert setup.
- **Returns:** job id, status, scores, output files, logs.

### REINVENT4 — `REINVENT4Adapter` (`reinvent_adapter.py`)
- **Enable:** install REINVENT4 from
  <https://github.com/MolecularAI/REINVENT4> into its own environment and set
  `REINVENT4_PYTHON` (interpreter) or `REINVENT4_BIN`.
- **Endpoints:** `POST /api/reinvent/create-config` (writes a real TOML config
  from scoring weights), `/run` (subprocess run if configured),
  `/parse-results` (parses generated SMILES + RDKit re-validation),
  `GET /api/reinvent/jobs/{id}`.
- **Note:** no RL training happens inside this app. Config generation is always
  real; a run without a configured runtime returns `CONFIGURED_BUT_NOT_RUN`.

## Governance adapters

### Safety — `SafetyAdapter` (`safety_adapter.py`)
Screens text/molecule outputs, quarantines hazardous content, redacts unsafe
details, and enforces the no-synthesis-route policy. See `SAFETY_POLICY.md`.

### Report — `ReportAdapter` (`report_adapter.py`)
Assembles a Markdown + JSON report from real tool runs, always embedding the
human-responsibility statement. `POST /api/report/generate`, `GET /api/report/{id}`.

## Health checks

`GET /api/tools/health` runs every adapter's `health_check()` and returns
`AVAILABLE` / `MISSING_DEPENDENCY` / `NOT_CONFIGURED` / `DEGRADED` / `ERROR` per
tool. The Tool Registry page renders this live — nothing is shown as connected
unless the backend confirms it.
