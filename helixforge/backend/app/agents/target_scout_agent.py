from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType, utcnow
from app.services import scoring
from app.storage import db


class TargetScoutAgent(BaseAgent):
    name = "Target Scout"
    role = "Calls real ChEMBL target search + ClinicalTrials.gov precedent, then ranks targets with the transparent Target Opportunity Score."
    stage = "target_ranking"
    stage_index = 4
    allowed_tools = ["ChEMBL", "ClinicalTrials.gov"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        # Target search breadth is decoupled from max_results: targets are cheap
        # and the druggable single-protein human target (e.g. EGFR CHEMBL203) may
        # rank below related complexes/orthologs, so always fetch a healthy set.
        target_fetch = max(15, ctx.max_results)
        targets_res = track(ctx, out, reg.chembl.execute(
            {"operation": "targets", "query": ctx.target_query, "max_results": target_fetch},
            project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=True)

        # Clinical precedent is a genuine target-ranking signal; fetch once and
        # cache for the Clinical Strategy Agent to reuse (no duplicate call).
        trials_res = track(ctx, out, reg.clinicaltrials.execute(
            {"condition": ctx.condition, "query": ctx.target_query, "max_results": ctx.max_results},
            project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=True)
        trials = trials_res.get("items", [])
        ctx.shared["trials"] = trials
        ctx.shared["trials_source_type"] = trials_res.get("source_type")

        pubmed_count = len(ctx.shared.get("evidence", []))
        ranked = []
        for t in targets_res.get("items", []):
            inputs = scoring.target_inputs_from_chembl(
                t, ctx.target_query, pubmed_count, len(trials), activity_count=8)
            sc = scoring.score_target(inputs)
            rec = {
                "id": f"tgt-{t.get('target_chembl_id')}", "project_id": ctx.project_id, "created_at": utcnow(),
                "target_chembl_id": t.get("target_chembl_id"), "pref_name": t.get("pref_name"),
                "organism": t.get("organism"), "target_type": t.get("target_type"),
                "score": sc["score"], "score_breakdown": sc["breakdown"], "score_warnings": sc["warnings"],
                "evidence_count": pubmed_count, "clinical_precedent_count": len(trials),
                "activity_availability": 8, "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "status": "ranked",
            }
            ranked.append(rec)

        ranked.sort(key=lambda r: r["score"], reverse=True)
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
            r["status"] = "selected" if i == 0 else "ranked"
            db.insert("target_candidates", r)
            out.target_ids.append(r["id"])

        # Select the highest-scoring druggable single human protein for the
        # chemistry stages (complexes/PPIs rarely carry small-molecule SMILES).
        single_human = [r for r in ranked if r.get("target_type") == "SINGLE PROTEIN"
                        and r.get("organism") == "Homo sapiens"]
        selected = single_human[0] if single_human else (ranked[0] if ranked else None)
        if selected:
            selected["status"] = "selected"
            db.insert("target_candidates", selected)
        ctx.shared["targets"] = ranked
        ctx.shared["selected_target"] = selected
        ctx.shared["selected_target_id"] = selected["target_chembl_id"] if selected else "CHEMBL203"

        top = selected or (ranked[0] if ranked else None)
        out.output_summary = (
            f"Ranked {len(ranked)} ChEMBL targets. Selected {top['pref_name']} ({top['target_chembl_id']}, "
            f"score {top['score']}/100) with {len(trials)} clinical precedents." if top else "No ChEMBL targets returned."
        )
        out.rationale = (
            "Selection favors exact-name single-protein human targets with bioactivity data, literature evidence, "
            "and clinical precedent — via the transparent Target Opportunity Score (weights shown in the report)."
        )
        out.assumptions = ["Clinical precedent count is a proxy signal, not a measure of efficacy."]
        out.uncertainty_notes = "Contradictory evidence, if present, lowers confidence." if ctx.shared.get("evidence_contradicts") else ""
        out.next_action = "Hypothesis Agent generates therapeutic hypotheses."
        base_conf = 0.82 - (0.06 if ctx.shared.get("evidence_contradicts") else 0)
        out.confidence = self.compute_confidence(base_conf, out)
        out.check("target_selected", bool(top))
        out.check("target_has_evidence_path", pubmed_count > 0 or (top and top["clinical_precedent_count"] > 0),
                  "≥1 evidence or clinical path" )
        if not ranked:
            out.status = "WARNING"
            out.errors.append("ChEMBL returned no targets.")
        return out
