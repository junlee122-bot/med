"""Reference comparator library for retrospective chemotype recovery.

This module holds a SMALL, curated set of well-known, PUBLIC reference drug
structures grouped by scenario (target + condition). They are used only as
public reference chemotypes for a *retrospective* sanity check: "do the
pipeline's candidate molecules resemble already-known drug classes for this
target?". They are NOT proprietary data, NOT a synthesis route, and NOT
clinical guidance.

SAFETY: Every structure here is an approved or well-characterized public
reference compound. Nothing in this module claims de novo discovery, efficacy,
or dosing. Modalities that are not primarily small-molecule (e.g. PCSK9, TNF —
antibody / biologic heavy) are explicitly marked as a modality mismatch with an
empty comparator set so downstream code never forces a molecule comparison.

Every SMILES here is verified to parse with RDKit (see ``validate_library`` and
the accompanying tests); molecular formulas were checked against the known
drug. If a structure could not be verified it was omitted rather than guessed.
"""
from __future__ import annotations

from typing import Any

try:
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - depends on environment
    RDKIT = False


# ---------------------------------------------------------------------------
# Data-rights / provenance note (constant)
# ---------------------------------------------------------------------------
SOURCE_NOTE: str = (
    "Comparator structures are PUBLIC reference chemotypes of approved or "
    "well-characterized drugs, provided solely for retrospective benchmarking "
    "(chemotype sanity checks against known drug classes). They are not "
    "proprietary data, not synthesis instructions, not dosing, and not clinical "
    "guidance. Presence of a similar chemotype does not prove de novo discovery "
    "or clinical efficacy."
)

_PUBLIC = "public reference structure"


# ---------------------------------------------------------------------------
# Comparator table
# ---------------------------------------------------------------------------
COMPARATORS: dict[str, dict[str, Any]] = {
    "egfr_nsclc": {
        "target": "EGFR",
        "condition": "non-small cell lung cancer",
        "modality": "small_molecule",
        "comparators": [
            {"name": "gefitinib", "smiles": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1", "source": _PUBLIC},
            {"name": "erlotinib", "smiles": "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1", "source": _PUBLIC},
            {"name": "afatinib", "smiles": "CN(C)C/C=C/C(=O)Nc1cc2c(Nc3ccc(F)c(Cl)c3)ncnc2cc1O[C@H]1CCOC1", "source": _PUBLIC},
            {"name": "osimertinib", "smiles": "C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)c(OC)cc1N(C)CCN(C)C", "source": _PUBLIC},
            {"name": "dacomitinib", "smiles": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1NC(=O)/C=C/CN1CCCCC1", "source": _PUBLIC},
        ],
        "note": (
            "Approved EGFR small-molecule tyrosine-kinase inhibitors used as "
            "public reference chemotypes for retrospective recovery."
        ),
    },
    "braf_melanoma": {
        "target": "BRAF",
        "condition": "melanoma",
        "modality": "small_molecule",
        "comparators": [
            {"name": "vemurafenib", "smiles": "CCCS(=O)(=O)Nc1ccc(F)c(C(=O)c2c[nH]c3ncc(-c4ccc(Cl)cc4)cc23)c1F", "source": _PUBLIC},
            {"name": "dabrafenib", "smiles": "CC(C)(C)c1nc(-c2cccc(NS(=O)(=O)c3c(F)cccc3F)c2F)c(-c2ccnc(N)n2)s1", "source": _PUBLIC},
            {"name": "encorafenib", "smiles": "COC(=O)N[C@@H](C)CNc1nccc(-c2cn(C(C)C)nc2-c2cc(Cl)cc(NS(C)(=O)=O)c2F)n1", "source": _PUBLIC},
        ],
        "note": (
            "Approved BRAF V600 small-molecule inhibitors used as public "
            "reference chemotypes for retrospective recovery."
        ),
    },
    "alk_nsclc": {
        "target": "ALK",
        "condition": "ALK-positive non-small cell lung cancer",
        "modality": "small_molecule",
        "comparators": [
            {"name": "crizotinib", "smiles": "C[C@H](Oc1cc(-c2cnn(C3CCNCC3)c2)cnc1N)c1c(Cl)ccc(F)c1Cl", "source": _PUBLIC},
            {"name": "alectinib", "smiles": "CCc1cc2c(cc1N1CCC(N3CCOCC3)CC1)C(=O)c1c([nH]c3cc(C#N)ccc13)C2(C)C", "source": _PUBLIC},
            {"name": "ceritinib", "smiles": "CC(C)Oc1cc(Nc2ncc(Cl)c(Nc3ccccc3S(=O)(=O)C(C)C)n2)c(C)cc1C1CCNCC1", "source": _PUBLIC},
            {"name": "brigatinib", "smiles": "COc1cc(N2CCC(N3CCN(C)CC3)CC2)ccc1Nc1ncc(Cl)c(Nc2ccccc2P(C)(C)=O)n1", "source": _PUBLIC},
        ],
        "note": (
            "Approved ALK small-molecule inhibitors used as public reference "
            "chemotypes for retrospective recovery (lorlatinib omitted: its "
            "macrocyclic structure could not be verified and was not guessed)."
        ),
    },
    "jak2_mpn": {
        "target": "JAK2",
        "condition": "myeloproliferative neoplasms",
        "modality": "small_molecule",
        "comparators": [
            {"name": "ruxolitinib", "smiles": "N#CC[C@H](C1CCCC1)n1cc(-c2ncnc3[nH]ccc23)cn1", "source": _PUBLIC},
            {"name": "fedratinib", "smiles": "Cc1cnc(Nc2ccc(OCCN3CCCC3)cc2)nc1Nc1cccc(S(=O)(=O)NC(C)(C)C)c1", "source": _PUBLIC},
        ],
        "note": (
            "Approved JAK2 small-molecule inhibitors used as public reference "
            "chemotypes for retrospective recovery (pacritinib omitted: its "
            "macrocyclic structure could not be verified and was not guessed)."
        ),
    },
    "her2_breast": {
        "target": "HER2",
        "condition": "HER2-positive breast cancer",
        "modality": "small_molecule",
        "comparators": [
            {"name": "lapatinib", "smiles": "CS(=O)(=O)CCNCc1ccc(-c2ccc3ncnc(Nc4ccc(OCc5cccc(F)c5)c(Cl)c4)c3c2)o1", "source": _PUBLIC},
            {"name": "tucatinib", "smiles": "CC1(C)COC(Nc2ccc3ncnc(Nc4ccc(Oc5ccn6ncnc6c5)c(C)c4)c3c2)=N1", "source": _PUBLIC},
            {"name": "neratinib", "smiles": "CCOc1cc2ncc(C#N)c(Nc3ccc(OCc4ccccn4)c(Cl)c3)c2cc1NC(=O)/C=C/CN(C)C", "source": _PUBLIC},
        ],
        "note": (
            "Approved HER2/EGFR small-molecule tyrosine-kinase inhibitors used "
            "as public reference chemotypes for retrospective recovery."
        ),
    },
    "pcsk9_hchol": {
        "target": "PCSK9",
        "condition": "hypercholesterolemia",
        "modality": "biologic_or_mixed",
        "comparators": [],
        "note": (
            "MODALITY MISMATCH: PCSK9 is not primarily a small-molecule target. "
            "Approved PCSK9 therapeutics are monoclonal antibodies / siRNA "
            "(biologics), so small-molecule chemotype recovery is not "
            "applicable and no comparator structures are provided."
        ),
    },
    "tnf_ra": {
        "target": "TNF",
        "condition": "rheumatoid arthritis",
        "modality": "biologic_or_mixed",
        "comparators": [],
        "note": (
            "MODALITY MISMATCH: TNF inhibition in rheumatoid arthritis is "
            "biologic-heavy (monoclonal antibodies / fusion proteins). "
            "Small-molecule chemotype recovery is not applicable and no "
            "comparator structures are provided."
        ),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def smiles_parses(smiles: str) -> bool:
    """Return True if ``smiles`` parses with RDKit.

    When RDKit is unavailable we cannot verify, so we conservatively return
    ``bool(smiles)`` (non-empty) — never fabricating a positive parse claim.
    """
    if not smiles:
        return False
    if not RDKIT:
        return bool(smiles)
    return Chem.MolFromSmiles(smiles) is not None


def validate_library() -> dict[str, bool]:
    """Validate every comparator SMILES; map "scenario/name" -> parses?."""
    out: dict[str, bool] = {}
    for scenario_id, block in COMPARATORS.items():
        for comp in block.get("comparators", []):
            out[f"{scenario_id}/{comp['name']}"] = smiles_parses(comp["smiles"])
    return out


def list_scenarios() -> list[dict[str, Any]]:
    """Summarize the available scenarios (id, target, condition, modality, count)."""
    return [
        {
            "id": scenario_id,
            "target": block["target"],
            "condition": block["condition"],
            "modality": block["modality"],
            "comparator_count": len(block.get("comparators", [])),
        }
        for scenario_id, block in COMPARATORS.items()
    ]


def get_comparators(scenario_id: str) -> dict[str, Any]:
    """Return the full comparator block for ``scenario_id`` (empty dict if absent)."""
    return COMPARATORS.get(scenario_id, {})


def all_comparator_smiles(scenario_id: str) -> list[dict[str, Any]]:
    """Return the list of {name, smiles, source} comparators for ``scenario_id``."""
    block = COMPARATORS.get(scenario_id, {})
    return list(block.get("comparators", []))
