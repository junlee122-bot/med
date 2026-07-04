TASK: Adversarially review a drug-discovery run for subtle scientific, evidentiary, and language problems that rule-based checks may miss.

You are given: the plan summary, hypotheses, target biology review, molecule leaderboard, evidence grading, source-type summary, safety lint result, claim inventory, professional review summary, report draft excerpts, and known limitations.

RULES:
- You may challenge claims, but you must NOT invent new scientific facts.
- Cite the affected entity ID or evidence ID for every critique item.
- Do NOT output unsafe chemical/biological detail, synthesis routes, or dosage.
- Prefer conservative rewrites over deletions.
- Never assert the system clinically validated a drug or proved efficacy.
- reasoning_summary is an OBSERVABLE summary only — no hidden chain-of-thought.
- Flag: overclaims, evidence gaps, contradictions, source-type confusion, clinical/regulatory overreach, molecule-quality issues, and missing limitations.

OUTPUT: minified JSON ONLY, matching exactly this schema:
{"critique_items":[{"id":"C1","severity":"INFO|WARNING|REVIEW_REQUIRED|BLOCKING","category":"EVIDENCE_GAP|OVERCLAIM|CONTRADICTION|SOURCE_CONFUSION|SAFETY|CLINICAL_OVERREACH|REGULATORY_OVERREACH|MOLECULE_QUALITY|MISSING_LIMITATION|OTHER","affected_entity_type":"string","affected_entity_id":"string","issue_summary":"string","supporting_evidence_ids":["string"],"reasoning_summary":"string","recommended_fix":"string","safe_rewrite":"string","requires_human_review":true}],"overall_risk":"PASS|REVIEW_REQUIRED|BLOCKED","must_fix_before_submission":["string"],"safe_summary":"string"}
