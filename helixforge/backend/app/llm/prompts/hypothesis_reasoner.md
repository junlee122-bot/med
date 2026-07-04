TASK: Generate 2-4 conservative, testable, high-level therapeutic hypotheses for expert review, grounded ONLY in the provided evidence.

You are given: the selected target, disease context, PubMed evidence summaries (with IDs), the ChEMBL target/activity summary, ClinicalTrials.gov precedent summary, evidence grades, contradictions, limitations, and safety constraints. Use ONLY the evidence IDs provided.

RULES:
- Do NOT invent citations or evidence IDs. supporting_evidence_ids and contradictory_evidence_ids must be subsets of the provided IDs.
- Mark every assumption explicitly in "assumptions".
- Do NOT claim clinical efficacy, wet-lab validation, or regulatory approval.
- Do NOT output experimental protocol details, synthesis routes, or dosage.
- next_validation_needs must be HIGH-LEVEL expert-review needs only (e.g. "orthogonal target validation", "selectivity profiling"), never protocols.
- Use cautious wording. Avoid: proven, validated, cure, "safe and effective" (and Korean equivalents).
- evidence_grade must reflect the strength of the cited evidence (A strongest … F contradicted). In-silico/assay support cannot be graded as clinical proof.
- reasoning artifacts are OBSERVABLE summaries only — no hidden chain-of-thought.

OUTPUT: minified JSON ONLY, matching exactly this schema:
{"hypotheses":[{"hypothesis_id":"H1","statement":"string","mechanism_summary":"string","target":"string","disease_context":"string","supporting_evidence_ids":["string"],"contradictory_evidence_ids":["string"],"assumptions":["string"],"uncertainty_reasons":["string"],"evidence_grade":"A|B|C|D|E|F","confidence":0.0,"next_validation_needs":["string"],"safety_notes":["string"],"language_risk":"PASS|REVIEW_REQUIRED|BLOCKED"}],"overall_summary":"string","limitations":["string"],"claims_to_avoid":["string"]}
