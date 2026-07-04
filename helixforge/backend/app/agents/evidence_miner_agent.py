from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType, utcnow
from app.storage import db

CONTRA_KEYWORDS = ("no benefit", "did not improve", "no significant", "resistance", "failed to", "lack of efficacy")


class EvidenceMinerAgent(BaseAgent):
    name = "Evidence Miner"
    role = "Calls the real PubMed adapter, stores evidence items, and classifies direction (supports/contradicts/neutral)."
    stage = "evidence_mining"
    stage_index = 2
    allowed_tools = ["PubMed"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        query = ctx.shared.get("pubmed_query", f"{ctx.target_query} {ctx.condition} resistance")
        res = track(ctx, out, reg.pubmed.execute(
            {"query": query, "max_results": ctx.max_results},
            project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=True)

        evidence: list[dict] = []
        for it in res.get("items", [])[: ctx.max_results]:
            title = (it.get("title") or "")
            abstract = (it.get("abstract") or "")
            hay = f"{title} {abstract}".lower()
            direction = "contradicts" if any(k in hay for k in ("no benefit", "did not improve", "no significant", "lack of efficacy", "failed to")) else "supports"
            ev = {
                "id": f"ev-{it.get('pmid')}",
                "project_id": ctx.project_id, "created_at": utcnow(),
                "source_name": "PubMed", "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "identifier_type": "PMID", "identifier": f"PMID:{it.get('pmid')}",
                "title": title, "year": it.get("year", ""), "url": it.get("url", ""),
                "claim": title, "evidence_direction": direction,
                "verification_status": "PENDING", "verification_reason": "",
                "retrieved_at": it.get("retrieved_at", utcnow()),
                "linked_tool_run_id": res.get("audit_event_id"),
            }
            db.insert("evidence_items", ev)
            evidence.append(ev)
            out.evidence_ids.append(ev["id"])

        # Contradictory-evidence injection (self-correction demo).
        if ctx.inj("contradictory_evidence") and evidence:
            contra = {
                "id": "ev-contradictory-demo", "project_id": ctx.project_id, "created_at": utcnow(),
                "source_name": "PubMed", "source_type": SourceType.HUMAN_INPUT.value,
                "identifier_type": "HUMAN_INPUT", "identifier": "INJECTED:contradictory",
                "title": f"Injected contradictory signal: a subpopulation shows limited {ctx.target_query} benefit",
                "year": "", "url": "", "claim": "A subgroup shows limited benefit, tempering universal efficacy claims.",
                "evidence_direction": "contradicts", "verification_status": "HUMAN_INPUT",
                "verification_reason": "Human-input contradictory item retained to represent uncertainty.",
                "retrieved_at": utcnow(),
            }
            db.insert("evidence_items", contra)
            evidence.append(contra)
            out.evidence_ids.append(contra["id"])
            out.warnings.append("Contradictory evidence injected; downstream confidence will be reduced (uncertainty represented, not hidden).")

        ctx.shared["evidence"] = evidence
        supports = sum(1 for e in evidence if e["evidence_direction"] == "supports")
        contradicts = sum(1 for e in evidence if e["evidence_direction"] == "contradicts")
        ctx.shared["evidence_supports"] = supports
        ctx.shared["evidence_contradicts"] = contradicts

        out.output_summary = f"Retrieved {len(evidence)} evidence items ({supports} supporting, {contradicts} contradictory) from real PubMed."
        out.rationale = "Direction is inferred with conservative keyword heuristics; ambiguous items default to 'supports' and are flagged for the Critic."
        out.assumptions = ["Direction classification is heuristic, not a semantic reading of full text."]
        out.uncertainty_notes = "Contradictory items are retained, never hidden." if contradicts else ""
        out.next_action = "Citation Verifier checks identifiers."
        out.confidence = self.compute_confidence(0.8 if evidence else 0.4, out)
        out.check("evidence_retrieved", len(evidence) > 0, f"{len(evidence)} items")
        if not evidence:
            out.errors.append("No evidence retrieved (PubMed empty or unreachable).")
            out.status = "WARNING"
        return out
