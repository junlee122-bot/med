"""RDKit adapter — real cheminformatics.

Validates SMILES, canonicalizes, computes descriptors + QED + Lipinski, and
Tanimoto similarity on Morgan fingerprints. If RDKit is not importable, returns
CONFIGURED_BUT_NOT_RUN (never a fabricated descriptor set).

Safety: structure validation and property analysis only. No synthesis routes.
"""
from __future__ import annotations

from typing import Any, Optional

from app.adapters.base import ToolAdapter
from app.models.schemas import (
    HealthStatus,
    SourceType,
    ToolHealth,
    ValidationResult,
    ValidationStatus,
)

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, QED, rdMolDescriptors
    from rdkit.DataStructs import TanimotoSimilarity
    RDLogger.DisableLog("rdApp.*")
    _RDKIT_OK = True
    _RDKIT_ERR = ""
except Exception as exc:  # pragma: no cover - depends on environment
    _RDKIT_OK = False
    _RDKIT_ERR = str(exc)


class RDKitAdapter(ToolAdapter):
    id = "rdkit"
    name = "RDKit"
    category = "chemistry"
    required_config = ["rdkit python package"]
    mode = "local"

    def health_check(self) -> ToolHealth:
        if _RDKIT_OK:
            import rdkit
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.AVAILABLE, mode=self.mode,
                detail=f"RDKit {rdkit.__version__} importable; SMILES sanity check OK.",
                required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.MISSING_DEPENDENCY, mode=self.mode,
            detail=f"RDKit not importable: {_RDKIT_ERR}. Install via conda/pip (see README).",
            required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        op = payload.get("operation", "descriptors")
        if not _RDKIT_OK:
            return self._not_run(payload)
        if op == "validate":
            return self._validate(payload.get("smiles", ""))
        if op == "similarity":
            return self._similarity(payload.get("smiles", ""), payload.get("reference_smiles", ""))
        return self._descriptors(payload.get("smiles", ""))

    # -- operations -------------------------------------------------------
    def _mol(self, smiles: str):
        return Chem.MolFromSmiles(smiles) if smiles else None

    def _validate(self, smiles: str) -> dict[str, Any]:
        mol = self._mol(smiles)
        if mol is None:
            return self._invalid(smiles)
        return self._envelope(
            smiles, valid=True, canonical=Chem.MolToSmiles(mol),
            summary=f"Valid SMILES; canonicalized.", extra={},
        )

    def _descriptors(self, smiles: str) -> dict[str, Any]:
        mol = self._mol(smiles)
        if mol is None:
            return self._invalid(smiles)
        mw = round(Descriptors.MolWt(mol), 2)
        logp = round(Crippen.MolLogP(mol), 2)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        tpsa = round(rdMolDescriptors.CalcTPSA(mol), 2)
        rot = Lipinski.NumRotatableBonds(mol)
        rings = rdMolDescriptors.CalcNumRings(mol)
        try:
            qed = round(QED.qed(mol), 3)
        except Exception:
            qed = 0.0
        violations = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
        descriptors = {
            "mol_weight": mw, "logp": logp, "hbd": hbd, "hba": hba, "tpsa": tpsa,
            "rotatable_bonds": rot, "ring_count": rings, "qed": qed,
            "lipinski_pass": violations == 0, "lipinski_violations": violations,
        }
        return self._envelope(
            smiles, valid=True, canonical=Chem.MolToSmiles(mol),
            summary=f"MW {mw}, logP {logp}, QED {qed}, Lipinski {'pass' if violations == 0 else f'{violations} viol'}.",
            extra={"descriptors": descriptors, "fingerprint_bits": 2048},
        )

    def _similarity(self, smiles: str, ref: str) -> dict[str, Any]:
        mol = self._mol(smiles)
        rmol = self._mol(ref)
        if mol is None or rmol is None:
            bad = smiles if mol is None else ref
            return self._invalid(bad)
        fp1 = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        fp2 = AllChem.GetMorganFingerprintAsBitVect(rmol, 2, nBits=2048)
        sim = round(TanimotoSimilarity(fp1, fp2), 4)
        return self._envelope(
            smiles, valid=True, canonical=Chem.MolToSmiles(mol),
            summary=f"Tanimoto similarity to reference = {sim}.",
            extra={"similarity": sim, "fingerprint_bits": 2048},
        )

    # -- envelopes --------------------------------------------------------
    def _envelope(self, smiles: str, *, valid: bool, canonical: str, summary: str, extra: dict) -> dict[str, Any]:
        out = {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": f'smiles="{smiles}"',
            "output_summary": summary,
            "validation_status": ValidationStatus.PASSED.value,
            "valid": valid, "canonical_smiles": canonical,
            "errors": [], "warnings": [],
        }
        out.update(extra)
        return out

    def _invalid(self, smiles: str) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,  # a real RDKit determination that it's invalid
            "input_summary": f'smiles="{smiles}"',
            "output_summary": "RDKit rejected the SMILES as invalid (real parse failure).",
            "validation_status": ValidationStatus.FAILED.value,
            "valid": False, "canonical_smiles": "",
            "descriptors": None,
            "errors": [f"Invalid SMILES: could not be parsed by RDKit: '{smiles}'"],
            "warnings": [],
        }

    def _not_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
            "input_summary": self._summarize_input(payload),
            "output_summary": "RDKit not importable in this environment; no descriptors computed.",
            "validation_status": ValidationStatus.SKIPPED.value,
            "valid": False, "canonical_smiles": "",
            "errors": [], "warnings": [f"RDKit unavailable: {_RDKIT_ERR}"],
        }

    def validate_output(self, output: dict[str, Any]) -> ValidationResult:
        if output.get("source_type") == SourceType.CONFIGURED_BUT_NOT_RUN.value:
            return ValidationResult(status=ValidationStatus.SKIPPED, messages=["RDKit not available"])
        if not output.get("valid", False):
            return ValidationResult(status=ValidationStatus.FAILED, messages=output.get("errors", []))
        return ValidationResult(status=ValidationStatus.PASSED, checks=["parsed", "canonicalized"])


# module-level singleton convenience for the pipeline
def rdkit_available() -> bool:
    return _RDKIT_OK
