# Data Rights & Third-Party Attribution

> Third-Party Data Notice: results derive from public sources (PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov, TDC). Attribution is retained per record. Recorded snapshots contain limited, sanitized data (dataset metadata only) for reproducible demo — verify upstream terms before public redistribution. See DATA_RIGHTS_AND_ATTRIBUTION.md.

This document discloses every third-party data source and software framework whose output flows through HelixForge AI, the attribution required, and the redistribution policy applied to recorded demo snapshots. Where exact upstream license terms are not independently verified in-repo, the status is `REVIEW_REQUIRED` — we do not assert a license we have not confirmed.

## Sources

| Source | Data used | Use in app | Attribution | Redistribution risk | Snapshot policy | Status |
|---|---|---|---|---|---|---|
| PubMed / NCBI E-utilities | literature metadata (PMID, title, abstract) | evidence mining | yes | medium | metadata only; small; timestamped | REVIEW_REQUIRED |
| ChEMBL (EMBL-EBI) | targets, molecules, activities (SMILES, pChEMBL) | target/molecule import & analysis | yes | medium | limited records; attribution retained | REVIEW_REQUIRED |
| ClinicalTrials.gov v2 | trial registry records (NCT, phase, status) | clinical precedent | yes | low | limited records; public registry | REVIEW_REQUIRED |
| Therapeutics Data Commons (PyTDC) | ADME/Tox dataset metadata | evaluation/training substrate (metadata only in snapshots) | yes | medium | metadata only; NOT full dataset rows | REVIEW_REQUIRED |
| RDKit | software (descriptors, fingerprints) | molecule validation/analysis | no | low | no data redistribution | PASS |
| AutoDock Vina | software | fixture docking (optional) | no | low | not bundled | PASS |
| REINVENT4 | software | config generation (optional) | no | low | not bundled | PASS |
| FastAPI / React / Vite / Tailwind | software frameworks | app | no | low | n/a | PASS |

## Review-required sources

The following sources are marked `REVIEW_REQUIRED`: upstream terms must be verified before any **public redistribution** of recorded snapshots that contain their data. In-app live use follows each provider's usage policy.

- **PubMed / NCBI E-utilities** — Follow NCBI usage policy; identify via NCBI_EMAIL. (https://www.ncbi.nlm.nih.gov/home/about/policies/)
- **ChEMBL (EMBL-EBI)** — ChEMBL data is CC-BY-SA style; verify before public redistribution. (https://chembl.gitbook.io/chembl-interface-documentation/about)
- **ClinicalTrials.gov v2** — US public registry. (https://clinicaltrials.gov/about-site/terms-conditions)
- **Therapeutics Data Commons (PyTDC)** — Individual datasets carry their own source licenses — check before redistribution. (https://tdcommons.ai/)

## Recorded snapshot policy

Recorded snapshots (`RECORDED_REAL_TOOL_OUTPUT`) exist so the demo runs offline if the network is unavailable during judging. They contain **limited, sanitized data** — dataset *metadata* only for TDC, and a small number of records for literature/registry sources — with attribution retained. They are **not** a redistribution of full upstream datasets. Verify upstream terms before publishing snapshots outside the competition context.

## Software licenses

- **RDKit** — https://github.com/rdkit/rdkit (BSD-3)
- **AutoDock Vina** — https://github.com/ccsb-scripps/AutoDock-Vina (Apache-2.0)
- **REINVENT4** — https://github.com/MolecularAI/REINVENT4 (Apache-2.0)
- **FastAPI / React / Vite / Tailwind** — MIT/BSD

_Programmatically generated from `app/services/data_rights.py`; endpoint: `GET /api/data-rights`._
