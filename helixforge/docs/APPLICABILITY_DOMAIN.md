# Applicability Domain and Uncertainty

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `applicability_domain.py` · **Endpoints:** `/api/applicability/{assess-molecule,run,molecule/*}`

**Method.** RDKit Morgan fingerprints (radius 2, 1024 bits), Tanimoto to a reference set. Nearest-neighbour similarity and mean top-k.

**Status.** IN_DOMAIN / BORDERLINE / OUT_OF_DOMAIN / UNKNOWN. Without a reference set the status is UNKNOWN (never assumed IN_DOMAIN). Very low NN similarity → OUT_OF_DOMAIN; near-duplicate → low-novelty note.

**Effect.** Out-of-domain and unknown lower downstream confidence — a model/score is not trusted outside the domain it was derived from. Run-level uses index-based leave-one-out so genuine duplicates are still detectable.
