# Third-Party Tools & Data Sources

HelixForge integrates public tools and data. Users are responsible for complying
with each source's terms of use and rate limits.

## Data APIs (read-only)

| Source | Use | Notes / Terms |
|---|---|---|
| **NCBI E-utilities (PubMed)** | Literature search | Identify yourself via `NCBI_EMAIL`; optional `NCBI_API_KEY` raises limits (3→10 req/s). Follow NCBI usage policy. |
| **ClinicalTrials.gov API v2** | Trial precedent | Public registry; read-only. |
| **ChEMBL web services (EMBL-EBI)** | Targets, molecules, activities | CC-BY-SA style attribution for ChEMBL data. |

## Scientific libraries

| Tool | License | Use |
|---|---|---|
| **RDKit** | BSD-3 | SMILES validation, descriptors, QED, Lipinski, Morgan fingerprints. |
| **Therapeutics Data Commons (PyTDC)** | MIT (datasets carry their own licenses) | ADME/Tox datasets as evaluation/training substrate. Individual datasets (e.g. AqSolDB, hERG, Ames) have their own source licenses — check before redistribution. |
| **AutoDock Vina** | Apache-2.0 | Fixture-based docking (optional; install separately). |
| **REINVENT4** (MolecularAI) | Apache-2.0 | Molecular generation (optional; external install). |

## Frameworks

FastAPI (MIT), Starlette (BSD-3), Pydantic (MIT), httpx (BSD-3), Uvicorn
(BSD-3); React (MIT), Vite (MIT), Tailwind CSS (MIT), lucide-react (ISC).

## Provenance & attribution

Every tool result is labeled with a `SourceType` and logged as a `ToolRun` +
`AuditEvent`. Retrieved records keep their identifiers (PMID/NCT/ChEMBL/DOI) and
retrieval timestamps so downstream claims are traceable to the original source.
Secrets (e.g. `NCBI_API_KEY`) are redacted from logs, URLs, and exports.
