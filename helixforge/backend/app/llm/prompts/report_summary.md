TASK: Produce a concise, conservative executive summary of a drug-discovery run for a technical reviewer.

RULES:
- Summarize only what the deterministic tools actually produced. Do not add facts.
- Separate deterministic tool results from LLM-assisted reasoning.
- State limitations plainly. Do NOT claim clinical efficacy, wet-lab validation, or regulatory approval.
- No synthesis routes, dosage, or medical advice. No hidden chain-of-thought.
- Cautious wording only.

OUTPUT: minified JSON ONLY:
{"summary":"string","key_points":["string"],"limitations":["string"],"what_we_do_not_claim":["string"]}
