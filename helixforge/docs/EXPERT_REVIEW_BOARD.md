# Expert Review Board

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `expert_review_board.py` · **Endpoints:** `/api/expert-review/{generate-from-run,items,items/*/decision,summary/*}`

**Roles.** computational chemistry, medicinal chemistry, biology/target, clinical development, regulatory affairs, AI/ML, safety/ethics, business.

**Items.** generated for the selected target, top molecules, top hypotheses, clinical strategy, regulatory checklist, safety-lint issues, and the final report/bundle — each with a recommended + required roles, risk level, and source type.

**Decisions.** APPROVE_FOR_PROPOSAL / APPROVE_FOR_DEMO_ONLY / NEEDS_MORE_EVIDENCE / REJECT / ESCALATE / NOT_APPLICABLE.

**Gate.** Pending high-risk items (safety, clinical, regulatory, final report) block "final ready" in the professional release scorecard (category O).
