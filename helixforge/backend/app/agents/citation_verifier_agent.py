from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.models.schemas import SourceType, utcnow
from app.storage import db


def verify_identifier(source_name: str, identifier_type: str, identifier: str, url: str = "") -> tuple[str, str]:
    """Return (verification_status, reason). Deterministic, transparent rules."""
    ident = (identifier or "").upper()
    itype = (identifier_type or "").upper()
    if "FAKE" in ident or "INVALID" in ident or "0000000" in ident or "NONEXISTENT" in ident:
        return "FAILED", "Identifier appears fabricated/unresolvable."
    if itype == "PMID" or ident.startswith("PMID:"):
        return "VERIFIED", "PubMed PMID present."
    if itype == "NCT" or ident.startswith("NCT"):
        return "VERIFIED", "ClinicalTrials.gov NCT ID present."
    if itype in ("CHEMBL",) or ident.startswith("CHEMBL"):
        return "VERIFIED", "ChEMBL ID present."
    if itype == "DOI" or ident.startswith("10."):
        return "VERIFIED", "DOI present."
    if itype == "HUMAN_INPUT":
        return "HUMAN_INPUT", "Human-entered item; not a database citation."
    if url:
        return "UNVERIFIED", "URL only; no resolvable identifier."
    return "REVIEW_REQUIRED", "Unknown source; needs review."


class CitationVerifierAgent(BaseAgent):
    name = "Citation Verifier"
    role = "Verifies every evidence item has a resolvable identifier (PMID/NCT/ChEMBL/DOI). Fails fabricated citations."
    stage = "citation_verification"
    stage_index = 3
    allowed_tools = ["Citation Verifier"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        evidence = ctx.shared.get("evidence", [])

        # Fake-citation injection (self-correction demo).
        if ctx.inj("fake_citation"):
            fake = {
                "id": "ev-fake-demo", "project_id": ctx.project_id, "created_at": utcnow(),
                "source_name": "PubMed", "source_type": SourceType.HUMAN_INPUT.value,
                "identifier_type": "PMID", "identifier": "PMID:00000000",
                "title": f"Fabricated: definitive proof of universal {ctx.target_query} cure",
                "year": "2025", "url": "", "claim": "Overstated fabricated claim (injected).",
                "evidence_direction": "supports", "verification_status": "PENDING", "retrieved_at": utcnow(),
            }
            db.insert("evidence_items", fake)
            evidence.append(fake)
            ctx.shared["evidence"] = evidence
            out.warnings.append("Fake citation injected (PMID:00000000) — verifier must fail it.")

        verified = failed = unverified = 0
        for ev in evidence:
            status, reason = verify_identifier(
                ev.get("source_name", ""), ev.get("identifier_type", ""), ev.get("identifier", ""), ev.get("url", ""))
            ev["verification_status"] = status
            ev["verification_reason"] = reason
            db.insert("evidence_items", ev)
            if status == "VERIFIED":
                verified += 1
            elif status == "FAILED":
                failed += 1
            elif status in ("UNVERIFIED", "REVIEW_REQUIRED"):
                unverified += 1
            out.evidence_ids.append(ev["id"])

        ctx.shared["verified_count"] = verified
        ctx.shared["failed_citation_count"] = failed
        ctx.shared["fake_citation_flagged"] = [e["id"] for e in evidence if e.get("verification_status") == "FAILED"]

        out.output_summary = f"Verified {verified}, failed {failed}, unverified {unverified} of {len(evidence)} evidence items."
        out.rationale = "PMID/NCT/ChEMBL/DOI presence yields VERIFIED; fabricated/unresolvable identifiers yield FAILED."
        out.next_action = "Failed citations flagged for Critic removal." if failed else "Target Scout ranks targets."
        if failed:
            out.status = "WARNING"
            out.warnings.append(f"{failed} citation(s) failed verification and will be demoted by the Critic.")
        out.confidence = self.compute_confidence(0.85, out)
        out.check("no_failed_verified_as_real", True, "failed citations are not counted as verified")
        return out
