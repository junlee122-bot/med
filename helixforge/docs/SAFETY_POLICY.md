# Safety Policy

HelixForge AI is **research decision support only**. It does not replace expert
scientific, clinical, regulatory, legal, or ethical review. **Final
responsibility belongs to the human research team.** This statement is attached
to every generated report.

The policy is enforced in code (`backend/app/adapters/safety_adapter.py`,
invoked by the Safety Gate and by every pipeline run) and surfaced in the
frontend Safety Gate page.

## Prohibited outputs (refused / redacted)

The system does **not** generate:

- Wet-lab protocols
- Reaction recipes, reaction conditions, or purification procedures
- Step-by-step synthesis routes or reagent lists for synthesis
- Dosage or medical advice
- Instructions to increase toxicity, lethality, harmful delivery, evasion, or
  misuse
- Controlled or hazardous-material production guidance

When a request or candidate triggers one of these categories, the safety adapter
returns `BLOCKED` (or `REVIEW_REQUIRED`), a redacted summary (no actionable
detail), and, where possible, a safe alternative. Blocked candidates cannot
enter a report's recommended set.

## Allowed scope

- High-level molecular **property** analysis (descriptors, QED, Lipinski)
- SMILES validation and structural sanity checks
- Public-database lookup (PubMed, ChEMBL, ClinicalTrials.gov)
- **Non-actionable** synthetic-feasibility summary (score only — never a route)
- ADMET **risk** summary (toxicity is screened, never optimized)
- Docking **score** summary
- Candidate prioritization for expert review
- High-level clinical / regulatory **planning**
- Audit logs and reports

## Anti-fabrication guarantees

- Every tool result is labeled with a `SourceType`. A tool that is missing or
  errored is reported as `CONFIGURED_BUT_NOT_RUN` / `TOOL_ERROR`, **never**
  upgraded to `REAL_TOOL_OUTPUT`.
- PubMed, ChEMBL, and ClinicalTrials.gov data are fetched live; the system does
  not invent identifiers, citations, or trial records.
- Docking and REINVENT4 results are only shown when a real run occurred.

## No-synthesis-route policy

Synthesis feasibility is summarized **only** (e.g. a feasibility score or
complexity estimate). Actionable routes, reagents, and conditions are
intentionally withheld. This applies to the REINVENT4 and any retrosynthesis
integrations.

## Auditability

Every tool call writes a `ToolRun` and an `AuditEvent` (agent, tool, event type,
source type, input/output summary, validation status, warnings, errors,
timestamp). The trail is queryable at `/api/audit/events` and included in report
JSON exports. The system exposes this **observable process trace** — not hidden
model chain-of-thought.

## Human responsibility statement (verbatim)

> This system is research decision support only. It does not replace expert
> scientific, clinical, regulatory, legal, or ethical review. Final
> responsibility belongs to the human research team.
