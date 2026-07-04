# Docking Protocol Governance

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `docking_protocol.py` · **Endpoints:** `/api/docking/protocol/{create,run/*,lint}`

**Modes.** FIXTURE_ONLY, JOB_SPEC_ONLY, REAL_VINA_FIXTURE_RUN, NOT_CONFIGURED, FUTURE_FULL_DOCKING.

**Record.** receptor/ligand prep status (default NOT_PERFORMED), binding-site/box definition, exhaustiveness, control ligands, redocking/decoy validation (NOT_PERFORMED unless actually done), scoring status, limitations.

**Lint.** A score without a defined box/binding site is BLOCKED. A score against an unprepared receptor is REVIEW_REQUIRED. "Binding proof" claims are rejected.

**Honesty.** No receptor-prep instructions, no fabricated scores. AutoDock Vina stays CONFIGURED_BUT_NOT_RUN unless installed. Docking is a prioritization signal, not binding proof.
