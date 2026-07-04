from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent

STAGES = [
    ("Disease Biology Agent", "disease_modeling"),
    ("Evidence Miner", "evidence_mining"),
    ("Citation Verifier", "citation_verification"),
    ("Target Scout", "target_ranking"),
    ("Hypothesis Agent", "hypothesis_generation"),
    ("Molecule Design Agent", "molecule_design"),
    ("Cheminformatics Validator", "structure_validation"),
    ("ADMET & Evaluation Grounding Agent", "admet_grounding"),
    ("Binding & Structure Agent", "binding"),
    ("Synthesis Feasibility Agent", "synthesis_feasibility"),
    ("Safety Auditor", "safety_audit"),
    ("Clinical Strategy Agent", "clinical_strategy"),
    ("Regulatory Reviewer", "regulatory_review"),
    ("Critic Agent", "critic_review"),
    ("Evaluation Agent", "evaluation"),
    ("Report Builder", "report_generation"),
]


class OrchestratorAgent(BaseAgent):
    name = "Project Orchestrator"
    role = "Decomposes the objective into a DAG, assigns stages to specialized agents, tracks state, and decides when to revise."
    stage = "planning"
    stage_index = 0
    allowed_tools = ["Planner"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        stages = [{"index": i + 1, "agent": a, "stage": s} for i, (a, s) in enumerate(STAGES)]
        deps = [{"from": STAGES[i][1], "to": STAGES[i + 1][1]} for i in range(len(STAGES) - 1)]
        plan = {
            "objective": f"Agentic evidence-grounded discovery for {ctx.target_query} / {ctx.condition}",
            "stages": stages,
            "assigned_agents": [a for a, _ in STAGES],
            "dependencies": deps,
        }
        ctx.shared["plan"] = plan
        active = [k for k, v in ctx.injections.items() if v]
        out.output_summary = (
            f"{len(STAGES)}-stage agentic workflow created for {ctx.target_query} / {ctx.condition} with "
            "evidence mining, target scoring, molecule screening, safety gate, evaluation, and report generation."
        )
        out.rationale = (
            "The objective is decomposed into a directed pipeline where each stage's artifacts gate the next. "
            "Deterministic chemistry/data tasks route to local tools (RDKit, TDC); evidence tasks route to public APIs "
            "(PubMed, ChEMBL, ClinicalTrials.gov); a critic loop revises failures."
        )
        out.assumptions = ["EGFR/NSCLC is used as the retrospective-rediscovery anchor scenario."]
        out.next_action = "Dispatch Disease Biology Agent."
        if active:
            out.warnings.append(f"Error injections enabled for self-correction demo: {', '.join(active)}")
        out.confidence = 0.9
        out.check("plan_has_stages", len(stages) == len(STAGES), f"{len(stages)} stages")
        return out
