"""Professional governance / model-documentation generator.

Produces reviewer-facing Markdown artifacts (model card, data card, risk
register, traceability matrix, validation protocol, "what we do not claim", …)
by summarizing the *real* current state of the system through the existing
services. Every document is honest by construction:

* configured-but-not-run tools (AutoDock Vina, REINVENT4) are described as
  ``CONFIGURED_BUT_NOT_RUN`` — never as completed real results;
* no wet-lab, clinical, regulatory, or synthesis content is ever emitted;
* every document embeds a bilingual human-responsibility disclaimer and the
  full source-type legend so a card can never be mistaken for validated fact.

The generator is deterministic: it reads state via best-effort service calls
(each wrapped so a missing/empty run degrades to honest "no run yet" text) and
never fabricates a metric.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from app.models.schemas import SourceType, utcnow
from app.storage import db

# ---------------------------------------------------------------------------
# Fixed strings (verbatim per governance requirements)
# ---------------------------------------------------------------------------
DISCLAIMER_EN = (
    "This system is research decision support only. It does not replace expert "
    "scientific, clinical, regulatory, legal, or ethical review. Final "
    "responsibility belongs to the human research team."
)
DISCLAIMER_KO = (
    "본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. "
    "최종 판단과 책임은 연구자에게 있습니다."
)
SOURCE_TYPE_LEGEND = (
    "REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · "
    "TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · "
    "SAFETY_REDACTED · HUMAN_INPUT"
)


# ---------------------------------------------------------------------------
# Document-type constants
# ---------------------------------------------------------------------------
class ProfessionalDocType:
    """String identifiers for every professional document this module emits."""

    SYSTEM_CARD = "SYSTEM_CARD"
    AGENT_CARD = "AGENT_CARD"
    TOOL_CARD = "TOOL_CARD"
    DATA_CARD = "DATA_CARD"
    MODEL_CARD = "MODEL_CARD"
    EVALUATION_CARD = "EVALUATION_CARD"
    RISK_REGISTER = "RISK_REGISTER"
    VALIDATION_PROTOCOL = "VALIDATION_PROTOCOL"
    TRACEABILITY_MATRIX = "TRACEABILITY_MATRIX"
    CHANGE_CONTROL_LOG = "CHANGE_CONTROL_LOG"
    SCIENTIFIC_WHITEPAPER = "SCIENTIFIC_WHITEPAPER"
    WHAT_WE_DO_NOT_CLAIM = "WHAT_WE_DO_NOT_CLAIM"
    REAL_VS_REPLAY_VS_NOT_RUN = "REAL_VS_REPLAY_VS_NOT_RUN"
    SCIENTIFIC_REVIEWER_BRIEF = "SCIENTIFIC_REVIEWER_BRIEF"
    BUSINESS_REVIEWER_BRIEF = "BUSINESS_REVIEWER_BRIEF"
    MODEL_GOVERNANCE_APPENDIX = "MODEL_GOVERNANCE_APPENDIX"
    DATA_GOVERNANCE_APPENDIX = "DATA_GOVERNANCE_APPENDIX"


ALL_DOC_TYPES: list[str] = [
    ProfessionalDocType.SYSTEM_CARD,
    ProfessionalDocType.AGENT_CARD,
    ProfessionalDocType.TOOL_CARD,
    ProfessionalDocType.DATA_CARD,
    ProfessionalDocType.MODEL_CARD,
    ProfessionalDocType.EVALUATION_CARD,
    ProfessionalDocType.RISK_REGISTER,
    ProfessionalDocType.VALIDATION_PROTOCOL,
    ProfessionalDocType.TRACEABILITY_MATRIX,
    ProfessionalDocType.CHANGE_CONTROL_LOG,
    ProfessionalDocType.WHAT_WE_DO_NOT_CLAIM,
    ProfessionalDocType.REAL_VS_REPLAY_VS_NOT_RUN,
    ProfessionalDocType.SCIENTIFIC_REVIEWER_BRIEF,
    ProfessionalDocType.BUSINESS_REVIEWER_BRIEF,
    ProfessionalDocType.MODEL_GOVERNANCE_APPENDIX,
    ProfessionalDocType.DATA_GOVERNANCE_APPENDIX,
]

# Representative set surfaced by :func:`bundle`.
_BUNDLE_SET: list[str] = [
    ProfessionalDocType.SYSTEM_CARD,
    ProfessionalDocType.DATA_CARD,
    ProfessionalDocType.MODEL_CARD,
    ProfessionalDocType.RISK_REGISTER,
    ProfessionalDocType.VALIDATION_PROTOCOL,
    ProfessionalDocType.TRACEABILITY_MATRIX,
    ProfessionalDocType.WHAT_WE_DO_NOT_CLAIM,
    ProfessionalDocType.REAL_VS_REPLAY_VS_NOT_RUN,
]


# ---------------------------------------------------------------------------
# Best-effort state gathering (never raises)
# ---------------------------------------------------------------------------
def _gather_state() -> dict[str, Any]:
    """Collect a small, honest snapshot of system state.

    Every probe is isolated: a missing/empty run or an unavailable dependency
    degrades to a truthful placeholder rather than crashing generation.
    """
    state: dict[str, Any] = {
        "run_count": 0,
        "evidence_claims": "no run yet",
        "medchem": "no run yet",
        "translational": "no run yet",
        "clinical": "no run yet",
        "governance": "not audited",
        "release": "not computed",
        "vina_bin": "",
        "reinvent4_bin": "",
        "data_rights": None,
    }

    try:
        state["run_count"] = len(db.list_records("workflow_runs", limit=50))
    except Exception:
        pass

    try:
        from app.config import get_settings

        s = get_settings()
        state["vina_bin"] = s.vina_bin or ""
        state["reinvent4_bin"] = s.reinvent4_bin or ""
    except Exception:
        pass

    try:
        from app.services import evidence_grading

        g = evidence_grading.grade_run(None)
        state["evidence_claims"] = (
            f"{g.get('total_claims', 0)} claims graded; "
            f"distribution={g.get('grade_distribution', {})}"
        )
    except Exception:
        pass

    try:
        from app.services import medchem_review

        m = medchem_review.review_run(None)
        state["medchem"] = (
            f"{m.get('count', 0)} molecules reviewed; "
            f"rdkit_available={m.get('rdkit_available')}"
        )
    except Exception:
        pass

    try:
        from app.services import translational_readiness

        t = translational_readiness.assess_run(None)
        state["translational"] = t.get("readiness_level", "no run yet")
    except Exception:
        pass

    try:
        from app.services import clinical_precedent_review

        c = clinical_precedent_review.review_run(None)
        state["clinical"] = c.get("summary") or c.get("status") or "reviewed"
    except Exception:
        pass

    try:
        from app.services import source_type_governance

        a = source_type_governance.audit()
        state["governance"] = a.get("status", "audited")
    except Exception:
        pass

    try:
        from app.services import release_readiness

        r = release_readiness.compute()
        state["release"] = f"{r.get('status', 'unknown')} (score {r.get('score', 0)})"
    except Exception:
        pass

    try:
        from app.services import data_rights

        state["data_rights"] = data_rights.list_records()
    except Exception:
        pass

    return state


def _footer() -> str:
    """Shared disclaimer + source-type legend embedded in every document."""
    return (
        "\n---\n\n"
        "### Source-type legend\n\n"
        f"`{SOURCE_TYPE_LEGEND}`\n\n"
        "Every value the system surfaces is tagged with one of the labels above so a "
        "reviewer can never confuse a real tool result with a fallback, a heuristic, "
        "or a tool that was configured but not run.\n\n"
        "### Human responsibility\n\n"
        f"> {DISCLAIMER_EN}\n\n"
        f"> {DISCLAIMER_KO}\n\n"
        f"_Document provenance: {SourceType.HEURISTIC_ANALYSIS.value} — a rule-based "
        "synthesis of current system state, not a tool or database result. No wet-lab, "
        "clinical, regulatory, or synthesis content is generated._\n"
    )


# ---------------------------------------------------------------------------
# Per-document builders — each returns (title, markdown_body_without_footer)
# ---------------------------------------------------------------------------
def _tool_status_line(state: dict[str, Any]) -> str:
    vina = state.get("vina_bin") or "(unset)"
    rein = state.get("reinvent4_bin") or "(unset)"
    return (
        f"AutoDock Vina (`vina_bin={vina}`) and REINVENT4 (`reinvent4_bin={rein}`) are "
        "**CONFIGURED_BUT_NOT_RUN** in this deployment: their adapters and honest health "
        "checks exist, but no docking or generative run has been executed. They are never "
        "reported as completed real results."
    )


def _system_card(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# System Card — HelixForge AI\n\n"
        "**Purpose.** HelixForge AI is a research decision-support system that fuses "
        "literature evidence, bioactivity data, clinical-trial precedent, and "
        "cheminformatics into a traceable, source-typed workflow for early target and "
        "molecule triage.\n\n"
        "## What it is\n"
        "- A multi-agent orchestration layer (planner, retriever, critic, reviewer) over "
        "real public tools (PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov, TDC, RDKit).\n"
        "- An evidence- and claim-grading layer that labels the strength of every statement.\n"
        "- A governance layer (source-type audit, safety lint, release readiness) that "
        "keeps outputs honest.\n\n"
        "## What it is not\n"
        "- Not a laboratory, clinical, or regulatory system. It performs no wet-lab work "
        "and makes no therapeutic determination.\n\n"
        "## Current observed state\n"
        f"- Workflow runs recorded: {state['run_count']}\n"
        f"- Evidence grading: {state['evidence_claims']}\n"
        f"- Translational readiness (capped): {state['translational']}\n"
        f"- Source-type governance: {state['governance']}\n"
        f"- Release readiness: {state['release']}\n\n"
        f"{_tool_status_line(state)}\n"
    )
    return "System Card — HelixForge AI", body


def _agent_card(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Agent Card\n\n"
        "**Agents.** The pipeline is decomposed into cooperating agents, each with a "
        "narrow, auditable responsibility:\n\n"
        "| Agent | Responsibility | Guardrail |\n"
        "|---|---|---|\n"
        "| Planner | Decompose the research question into tool steps | Cannot invent data |\n"
        "| Retriever | Call real tools and attach source types | Every output carries a source label |\n"
        "| Critic | Challenge weak or unsupported claims | Forces evidence re-grading |\n"
        "| Reviewer | Assemble human-facing summary | Applies safety + overclaim lint |\n\n"
        "Each agent action is written to the audit log with its `source_type`, inputs, "
        "outputs, and any warnings. Agents never bypass the safety lint and never assert "
        "clinical or regulatory conclusions.\n\n"
        f"Observed: {state['run_count']} recorded workflow run(s); "
        f"evidence grading — {state['evidence_claims']}.\n"
    )
    return "Agent Card", body


def _tool_card(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Tool Card\n\n"
        "Real, live-callable tools and their integration mode:\n\n"
        "| Tool | Provider | Mode | Source type |\n"
        "|---|---|---|---|\n"
        "| PubMed / E-utilities | NCBI | HTTP (live) | REAL_TOOL_OUTPUT / RECORDED_REAL_TOOL_OUTPUT |\n"
        "| ChEMBL | EMBL-EBI | HTTP (live) | REAL_TOOL_OUTPUT / RECORDED_REAL_TOOL_OUTPUT |\n"
        "| ClinicalTrials.gov v2 | NIH | HTTP (live) | REAL_TOOL_OUTPUT / RECORDED_REAL_TOOL_OUTPUT |\n"
        "| TDC / PyTDC | Harvard | Python (metadata) | REAL_TOOL_OUTPUT |\n"
        "| RDKit | OSS | In-process | REAL_TOOL_OUTPUT |\n"
        "| AutoDock Vina | CCSB Scripps | Subprocess | CONFIGURED_BUT_NOT_RUN |\n"
        "| REINVENT4 | MolecularAI | Subprocess | CONFIGURED_BUT_NOT_RUN |\n\n"
        f"{_tool_status_line(state)}\n"
    )
    return "Tool Card", body


def _data_card(state: dict[str, Any]) -> tuple[str, str]:
    lines = [
        "# Data Card\n",
        "This card enumerates the data **sources** that flow through HelixForge AI, the "
        "type of data taken from each, and the **rights / attribution** posture for each. "
        "Where a license could not be verified, the source is marked `REVIEW_REQUIRED` "
        "rather than asserting a license.\n",
        "## Sources, data types, and rights",
        "",
        "| Source | Data type | Attribution required | Rights status |",
        "|---|---|---|---|",
    ]
    dr = state.get("data_rights")
    review_required: list[str] = []
    if isinstance(dr, dict) and dr.get("records"):
        for rec in dr["records"]:
            src = rec.get("source", "?")
            dtype = rec.get("data_type", "?")
            attr = "Yes" if rec.get("attribution_required") else "No"
            status = rec.get("status", "REVIEW_REQUIRED")
            lines.append(f"| {src} | {dtype} | {attr} | {status} |")
        review_required = dr.get("review_required_sources", []) or []
    else:
        # Honest fallback if data_rights is unavailable.
        for src, dtype in [
            ("PubMed / NCBI", "literature metadata (PMID, title, abstract)"),
            ("ChEMBL / EMBL-EBI", "targets, molecules, activities (SMILES, pChEMBL)"),
            ("ClinicalTrials.gov", "trial registry records (NCT, phase, status)"),
            ("TDC / PyTDC", "ADME/Tox dataset metadata"),
            ("RDKit", "cheminformatics software (descriptors, fingerprints)"),
        ]:
            lines.append(f"| {src} | {dtype} | see upstream | REVIEW_REQUIRED |")
        review_required = ["PubMed / NCBI", "ChEMBL / EMBL-EBI", "ClinicalTrials.gov", "TDC / PyTDC"]

    lines += [
        "",
        "## Rights and attribution note",
        "",
        "Attribution is retained per record. Recorded snapshots contain only limited, "
        "sanitized data (dataset metadata only where applicable) for reproducible demo — "
        "verify upstream source terms before any public redistribution.",
        "",
        f"Sources currently flagged `REVIEW_REQUIRED` (license unverified): "
        f"{', '.join(review_required) if review_required else 'none recorded'}.",
        "",
        "## Data handling",
        "",
        "- No patient-level or personally identifying data is ingested.",
        "- Snapshots store metadata only; they are not a redistribution of full datasets.",
        "- Every ingested record is source-typed so provenance is traceable end-to-end.",
        "",
    ]
    return "Data Card", "\n".join(lines)


def _model_card(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Model Card\n\n"
        "## Intended use\n"
        "Research decision support for early-stage target and molecule triage: "
        "prioritizing hypotheses, organizing public evidence, and flagging where expert "
        "review is required. Outputs are inputs to human scientific judgement.\n\n"
        "## Out-of-scope uses\n"
        "- Any clinical, diagnostic, or treatment decision.\n"
        "- Any regulatory submission as a source of validated fact.\n"
        "- Synthesis planning, dosing, or wet-lab protocol design.\n"
        "- Autonomous decision-making without a human in the loop.\n\n"
        "## Data\n"
        "Public literature, bioactivity, and trial-registry data plus RDKit-derived "
        "cheminformatics descriptors. See the Data Card for sources, types, and rights.\n\n"
        "## Evaluation approach\n"
        "Retrospective rediscovery of known target/molecule associations, citation-"
        "integrity checks, molecule-validity checks, self-correction (critic) counts, and "
        "source-type governance audits. Metrics are descriptive, not inferential.\n\n"
        "## Applicability domain\n"
        "Reliability is highest for well-studied oncology targets with abundant public "
        "data (e.g. EGFR/NSCLC) and degrades for sparse or novel targets. Predictions "
        "outside the training/support distribution are flagged as out-of-domain.\n\n"
        "## LIMITATIONS\n"
        "- No clinical or regulatory validation has been performed; the system is not a "
        "medical device and its outputs are not clinical conclusions.\n"
        "- Heuristic and computational signals are not experimental proof; assay evidence "
        "is not therapeutic efficacy.\n"
        "- Small evaluation samples preclude claims of statistical significance.\n"
        "- Coverage and correctness depend on upstream public databases, which may be "
        "incomplete, delayed, or inconsistent.\n"
        "- Configured-but-not-run generative/docking tools contribute no results here.\n\n"
        f"Observed state: {state['evidence_claims']}; medchem — {state['medchem']}.\n"
    )
    return "Model Card", body


def _evaluation_card(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Evaluation Card\n\n"
        "Evaluations are **descriptive** and offline-safe. None assert therapeutic effect.\n\n"
        "| Study | What it measures | Reported as |\n"
        "|---|---|---|\n"
        "| Retrospective rediscovery | Whether known associations resurface | Recall on a small known set |\n"
        "| Citation integrity | Whether cited PMIDs/NCTs resolve | Pass/fail counts |\n"
        "| Molecule validity | RDKit parse + druglikeness | Valid fraction |\n"
        "| Self-correction | Critic-triggered revisions | Revision counts |\n"
        "| Source-type governance | Mislabeling of provenance | Audit status |\n\n"
        "Sample sizes are intentionally small; results support qualitative confidence and "
        "reviewer prioritization, not statistical inference.\n\n"
        f"Observed governance status: {state['governance']}; release: {state['release']}.\n"
    )
    return "Evaluation Card", body


def _risk_register(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Risk Register\n\n"
        "Key risks and their mitigation. Safety and honesty risks are treated as "
        "first-class.\n\n"
        "| # | Risk | Impact | Mitigation |\n"
        "|---|---|---|---|\n"
        "| 1 | Hallucinated citation | A claim rests on a non-existent reference | "
        "Citation-integrity check resolves every PMID/NCT; unresolved citations force a "
        "grade downgrade |\n"
        "| 2 | Overclaim | Strong language beyond the evidence | Overclaim / scientific-"
        "language lint plus claim grading soften phrasing to match evidence strength |\n"
        "| 3 | Source mislabeling | A fallback shown as a real result | Source-type "
        "governance audit flags any REAL vs RECORDED conflict or missing label |\n"
        "| 4 | Out-of-domain prediction | Confident output outside the applicability "
        "domain | Applicability-domain check flags OOD inputs for expert review |\n"
        "| 5 | Configured-not-run misread as real | Vina/REINVENT4 assumed to have run | "
        "Tools are labeled CONFIGURED_BUT_NOT_RUN and audited against completed-result "
        "language |\n"
        "| 6 | Safety / forbidden-content leakage | Synthesis, dosing, or hazardous "
        "content emitted | Safety lint blocks forbidden categories; SAFETY_REDACTED "
        "labeling and human-responsibility disclaimer are mandatory |\n"
        "| 7 | Data-rights violation | Redistribution beyond license | Rights records mark "
        "unverified licenses REVIEW_REQUIRED; snapshots store metadata only |\n\n"
        "Each mitigation is exercised by an automated check; residual risk is carried to "
        "the human research team.\n\n"
        f"Observed source-type governance status: {state['governance']}.\n"
    )
    return "Risk Register", body


def _validation_protocol(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Validation Protocol\n\n"
        "This protocol describes how HelixForge AI is evaluated. It is a software and "
        "evidence-integrity protocol — it makes no claim of therapeutic or clinical "
        "validation.\n\n"
        "## Studies and metrics\n"
        "1. **Retrospective rediscovery.** For a small, curated set of known "
        "target/molecule associations, measure whether the pipeline resurfaces them. "
        "Reported as recall over the known set.\n"
        "2. **Citation integrity.** Every cited PMID and NCT is resolved against its "
        "source; report the pass/fail count and any unresolved references.\n"
        "3. **Molecule validity.** RDKit parses each candidate; report the valid fraction "
        "and druglikeness distribution.\n"
        "4. **Self-correction.** Count critic-triggered revisions to show the loop "
        "actively downgrades weak claims.\n"
        "5. **Source-type governance.** Audit stored records for provenance mislabeling "
        "and report the audit status.\n\n"
        "## Interpretation and honesty constraints\n"
        "- Sample sizes are intentionally small; they are insufficient to claim "
        "statistical significance, and results are read qualitatively.\n"
        "- Rediscovery recall reflects retrieval and organization quality, not any "
        "therapeutic property of a molecule.\n"
        "- No study here demonstrates efficacy; assay-level evidence is not clinical "
        "outcome, and no result should be read as such.\n\n"
        f"Observed: evidence grading — {state['evidence_claims']}; release — {state['release']}.\n"
    )
    return "Validation Protocol", body


def _traceability_matrix(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Traceability Matrix\n\n"
        "Each requirement is linked to the module that implements it and to the evidence "
        "(a test or an endpoint) that verifies it.\n\n"
        "| Requirement | Implementing feature / module | Evidence / verification |\n"
        "|---|---|---|\n"
        "| Every tool result is source-typed | `models.schemas.SourceType`, adapters | "
        "`source_type_governance.audit()`; governance tests |\n"
        "| Claims are graded by evidence strength | `services.evidence_grading` | "
        "`test_evidence_grading.py` |\n"
        "| Citations must resolve | evidence linter | citation-integrity checks / tests |\n"
        "| Molecules are validity-checked | `services.medchem_review` (RDKit) | "
        "`test_activity_medchem_applicability.py` |\n"
        "| Readiness never implies wet-lab success | `services.translational_readiness` | "
        "`test_translational.py` (capped at TRL_4) |\n"
        "| No forbidden/synthesis content | `services.safety_lint` | `test_red_team.py` / "
        "`test_security.py` |\n"
        "| Configured-not-run tools stay honest | Vina/REINVENT4 adapters | this "
        "traceability + governance audit |\n\n"
        "The matrix lets a reviewer walk from any requirement to the code and the "
        "verification that demonstrates it.\n\n"
        f"Observed governance status: {state['governance']}.\n"
    )
    return "Traceability Matrix", body


def _change_control_log(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Change Control Log\n\n"
        "Material changes to models, data sources, prompts, or safety rules are recorded "
        "with rationale and reviewer. This log is illustrative of the control, not a "
        "substitute for the version-control history.\n\n"
        "| Change class | Control | Reviewer of record |\n"
        "|---|---|---|\n"
        "| New data source | Add rights record; mark REVIEW_REQUIRED until verified | Data steward |\n"
        "| Model/heuristic change | Re-run evaluation studies; compare deltas | Scientific reviewer |\n"
        "| Safety-rule change | Re-run red-team + safety lint | Safety reviewer |\n"
        "| Prompt/agent change | Re-run rediscovery + self-correction checks | Scientific reviewer |\n\n"
        "No change may weaken the safety lint or relabel a CONFIGURED_BUT_NOT_RUN tool as "
        "a completed real result.\n"
    )
    return "Change Control Log", body


def _what_we_do_not_claim(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# What We Do NOT Claim\n\n"
        "To keep the system honest, we state explicitly what HelixForge AI does not do. "
        "We do not claim any of the following:\n\n"
        "- We do not claim any **wet-lab** validation of any target or molecule.\n"
        "- We do not claim clinical efficacy, safety, or therapeutic benefit.\n"
        "- We do not claim regulatory approval or regulatory compliance of any kind.\n"
        "- We do not claim binding proof or any experimentally confirmed interaction.\n"
        "- We do not provide dosing, medical advice, or treatment recommendations.\n"
        "- We do not provide synthesis routes or reagent/reaction procedures.\n"
        "- We do not claim statistical significance from our small evaluation samples.\n\n"
        "Each of the phrases above appears here only as something we explicitly do **not** "
        "claim. Outputs are hypotheses and organized public evidence for expert review — "
        "nothing more.\n"
    )
    return "What We Do NOT Claim", body


def _real_vs_replay_vs_not_run(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Real vs Replay vs Not-Run\n\n"
        "A single, unambiguous three-way classification of where every result comes from.\n\n"
        "| Class | Meaning | Tools / sources | Source type |\n"
        "|---|---|---|---|\n"
        "| REAL (live) | Executed now against the live source | PubMed, ChEMBL, "
        "ClinicalTrials.gov, RDKit, TDC | REAL_TOOL_OUTPUT |\n"
        "| RECORDED replay | Replayed from a captured real snapshot (metadata only) | "
        "Snapshotted PubMed/ChEMBL/ClinicalTrials/TDC records | RECORDED_REAL_TOOL_OUTPUT |\n"
        "| CONFIGURED_BUT_NOT_RUN | Integrated and health-checked, but not executed | "
        "AutoDock Vina, REINVENT4 | CONFIGURED_BUT_NOT_RUN |\n\n"
        "RECORDED replay data is clearly distinguished from live REAL results and is never "
        "relabeled as REAL. CONFIGURED_BUT_NOT_RUN tools are never described as having "
        "produced results.\n\n"
        f"{_tool_status_line(state)}\n"
    )
    return "Real vs Replay vs Not-Run", body


def _scientific_reviewer_brief(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Scientific Reviewer Brief\n\n"
        "For the scientific reviewer, in one page:\n\n"
        "- **Scope.** Early target/molecule triage from public evidence; a decision-"
        "support aid, not a discovery engine.\n"
        "- **Trust model.** Every claim is graded (A–F) by evidence strength; assay and "
        "computational signals are capped below clinical grades.\n"
        "- **What to check first.** Applicability domain (is the target well-studied?), "
        "citation integrity, and any out-of-domain flags.\n"
        "- **Honesty rails.** Source-type governance, safety lint, and translational "
        "readiness capped at TRL_4 (no wet-lab implied).\n\n"
        f"Observed: evidence — {state['evidence_claims']}; readiness — {state['translational']}; "
        f"clinical precedent — {state['clinical']}.\n"
    )
    return "Scientific Reviewer Brief", body


def _business_reviewer_brief(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Business Reviewer Brief\n\n"
        "For the business reviewer, in one page:\n\n"
        "- **Value.** Faster, better-organized, fully traceable early triage of public "
        "scientific evidence, with honesty guarantees that de-risk downstream review.\n"
        "- **Differentiator.** End-to-end source typing and claim grading — no black-box "
        "assertions; every output is auditable.\n"
        "- **Boundaries.** No clinical, regulatory, or wet-lab claims; value is upstream "
        "prioritization and evidence organization.\n"
        "- **Readiness.** " + str(state["release"]) + ".\n\n"
        "Business impact statements are assumption-heavy and graded accordingly; they are "
        "not evidence-backed conclusions.\n"
    )
    return "Business Reviewer Brief", body


def _model_governance_appendix(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Model Governance Appendix\n\n"
        "- **Provenance.** Every model/heuristic output is source-typed; baseline models "
        "are labeled BASELINE_MODEL_OUTPUT and never described as validated.\n"
        "- **Evaluation cadence.** Studies re-run on any model, prompt, or safety change "
        "(see Change Control Log).\n"
        "- **Applicability domain.** Enforced and surfaced; OOD inputs are flagged.\n"
        "- **Human oversight.** A human reviewer is required before any downstream use.\n\n"
        f"Observed governance status: {state['governance']}.\n"
    )
    return "Model Governance Appendix", body


def _data_governance_appendix(state: dict[str, Any]) -> tuple[str, str]:
    body = (
        "# Data Governance Appendix\n\n"
        "- **Sources and rights.** See the Data Card; unverified licenses are marked "
        "REVIEW_REQUIRED, and attribution is retained per record.\n"
        "- **Minimization.** No patient-level or personal data; snapshots store metadata "
        "only.\n"
        "- **Retention.** Records are timestamped and source-typed for auditability.\n"
        "- **Redistribution.** Verify upstream terms before any public redistribution.\n"
    )
    return "Data Governance Appendix", body


_BUILDERS: dict[str, Callable[[dict[str, Any]], tuple[str, str]]] = {
    ProfessionalDocType.SYSTEM_CARD: _system_card,
    ProfessionalDocType.AGENT_CARD: _agent_card,
    ProfessionalDocType.TOOL_CARD: _tool_card,
    ProfessionalDocType.DATA_CARD: _data_card,
    ProfessionalDocType.MODEL_CARD: _model_card,
    ProfessionalDocType.EVALUATION_CARD: _evaluation_card,
    ProfessionalDocType.RISK_REGISTER: _risk_register,
    ProfessionalDocType.VALIDATION_PROTOCOL: _validation_protocol,
    ProfessionalDocType.TRACEABILITY_MATRIX: _traceability_matrix,
    ProfessionalDocType.CHANGE_CONTROL_LOG: _change_control_log,
    ProfessionalDocType.WHAT_WE_DO_NOT_CLAIM: _what_we_do_not_claim,
    ProfessionalDocType.REAL_VS_REPLAY_VS_NOT_RUN: _real_vs_replay_vs_not_run,
    ProfessionalDocType.SCIENTIFIC_REVIEWER_BRIEF: _scientific_reviewer_brief,
    ProfessionalDocType.BUSINESS_REVIEWER_BRIEF: _business_reviewer_brief,
    ProfessionalDocType.MODEL_GOVERNANCE_APPENDIX: _model_governance_appendix,
    ProfessionalDocType.DATA_GOVERNANCE_APPENDIX: _data_governance_appendix,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate(doc_type: str) -> dict[str, Any]:
    """Generate one professional document.

    Args:
        doc_type: one of the :class:`ProfessionalDocType` constants.

    Returns:
        A dict with ``id``, ``doc_type``, ``title``, ``markdown``,
        ``source_type`` (always ``HEURISTIC_ANALYSIS``), and ``created_at``.
        Best-effort persisted to the ``professional_documents`` table.
    """
    state = _gather_state()
    builder = _BUILDERS.get(doc_type)
    if builder is None:
        title = doc_type.replace("_", " ").title()
        body = (
            f"# {title}\n\n"
            "This professional document type is defined but has no specialized template; "
            "the honest default content and governance rails still apply.\n"
        )
    else:
        title, body = builder(state)

    markdown = body + _footer()
    record: dict[str, Any] = {
        "id": f"pdoc-{uuid.uuid4().hex[:8]}",
        "doc_type": doc_type,
        "title": title,
        "markdown": markdown,
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": utcnow(),
    }
    try:
        db.insert("professional_documents", record)
    except Exception:
        pass
    return record


def list_docs(limit: int = 100) -> list[dict[str, Any]]:
    """Return recently generated professional documents (most recent first)."""
    try:
        return db.list_records("professional_documents", limit=limit)
    except Exception:
        return []


def bundle() -> dict[str, Any]:
    """Generate a representative set of documents as one reviewer bundle.

    Returns:
        A dict with ``generated_at``, ``documents`` (doc_type -> markdown),
        ``disclaimer``, and ``note``. The document set always contains at least
        the eight core governance documents.
    """
    documents: dict[str, str] = {}
    for doc_type in _BUNDLE_SET:
        try:
            documents[doc_type] = generate(doc_type)["markdown"]
        except Exception:
            documents[doc_type] = (
                f"# {doc_type}\n\nGeneration failed; no fabricated content emitted.\n"
                + _footer()
            )
    return {
        "generated_at": utcnow(),
        "documents": documents,
        "disclaimer": f"{DISCLAIMER_EN}\n\n{DISCLAIMER_KO}",
        "note": (
            "Rule-based (HEURISTIC_ANALYSIS) synthesis of current system state for expert "
            "review. No wet-lab, clinical, regulatory, or synthesis content is generated; "
            "configured-but-not-run tools are reported honestly."
        ),
    }
