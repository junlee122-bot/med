TASK: Produce a structured, safe execution plan for an in-silico drug-discovery run.

You are given: the disease/condition, target query, scenario preset, the available tools and their health status, the run mode, budget, safety strictness, user goals, and any previous failures. Select which pipeline stages to run and in what order, respecting dependencies and tool availability.

HARD CONSTRAINTS:
- Evidence mining must precede hypothesis reasoning.
- Target selection must precede molecule screening.
- RDKit validation must precede any molecule recommendation.
- Safety audit must run before report export.
- Claim inventory must run before final proposal lock.
- If LLM hypotheses are used, citation verification and evidence grading must follow them.
- If Vina/REINVENT4 are unavailable, mark them optional / configured-not-run — never required.
- You may NOT add wet-lab, synthesis, reaction-condition, dosage, or medical-advice stages.
- Always include a deterministic fallback path.
- rationale_summary fields are OBSERVABLE summaries only — no hidden chain-of-thought.

Choose stage_id values ONLY from this catalog:
tool_health, dynamic_plan, evidence_mining, chembl_target_search, clinical_precedent, target_selection, evidence_grading, hypothesis_reasoning, chembl_activities, rdkit_validation, activity_normalization, medchem_review, applicability_domain, pareto_analysis, true_rediscovery, optimization_loop, safety_lint, semantic_critic, claim_inventory, professional_review, report_build, hybrid_snapshot.

OUTPUT: minified JSON ONLY, matching exactly this schema:
{"objective":"string","strategy_summary":"string","mode":"HYBRID_LLM_DEV|HYBRID_FABLE_FINAL|DETERMINISTIC_ONLY","selected_stages":[{"stage_id":"string","agent":"string","purpose":"string","required_tools":["string"],"optional_tools":["string"],"depends_on":["string"],"success_criteria":["string"],"failure_recovery":["string"],"safety_constraints":["string"],"budget_class":"low|medium|high","rationale_summary":"string"}],"skipped_stages":[{"stage_id":"string","reason":"string"}],"replanning_triggers":["string"],"expected_artifacts":["string"],"risks":["string"],"cost_guard":{"estimated_llm_calls":0,"estimated_cost_usd":0.0}}
