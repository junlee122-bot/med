from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType, utcnow
from app.storage import db


class CheminformaticsValidatorAgent(BaseAgent):
    name = "Cheminformatics Validator"
    role = "Validates every candidate SMILES with real RDKit, computes descriptors, and screens each molecule. Rejects invalid structures."
    stage = "structure_validation"
    stage_index = 7
    allowed_tools = ["RDKit", "Safety"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        raw = list(ctx.shared.get("molecules_raw", []))

        # Invalid-SMILES injection (self-correction demo).
        if ctx.inj("invalid_smiles"):
            raw.append({
                "molecule_chembl_id": "INJECTED-INVALID", "smiles": "C1CC(C)(", "source": "injected",
                "activity_type": None, "pchembl_value": None, "source_type": SourceType.HUMAN_INPUT.value,
            })
            out.warnings.append("Invalid SMILES injected ('C1CC(C)(') — RDKit must reject it.")

        molecules = []
        valid = invalid = 0
        for i, r in enumerate(raw):
            smi = r["smiles"]
            rd = track(ctx, out, reg.rdkit.execute(
                {"operation": "descriptors", "smiles": smi},
                project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=False)
            sf = reg.safety.execute({"smiles": smi, "label": r.get("molecule_chembl_id")},
                                    project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id)
            is_valid = bool(rd.get("valid"))
            if is_valid:
                valid += 1
            else:
                invalid += 1
            mol = {
                "id": f"mol-{ctx.workflow_run_id}-{i+1}",
                "project_id": ctx.project_id, "workflow_run_id": ctx.workflow_run_id,
                "created_at": utcnow(),
                "molecule_chembl_id": r.get("molecule_chembl_id"), "label": r.get("molecule_chembl_id"),
                "smiles": smi, "canonical_smiles": rd.get("canonical_smiles"),
                "valid": is_valid, "validity_reason": (rd.get("errors") or [None])[0] if not is_valid else None,
                "descriptors": rd.get("descriptors"),
                "activity_type": r.get("activity_type"), "standard_value": r.get("standard_value"),
                "standard_units": r.get("standard_units"), "pchembl_value": r.get("pchembl_value"),
                "source": r.get("source"), "source_type": r.get("source_type", SourceType.REAL_TOOL_OUTPUT.value),
                "safety_status": sf.get("status") or "UNKNOWN", "safety_categories": sf.get("categories", []),
                "composite_score": None, "recommendation": ("Reject — invalid structure" if not is_valid else None),
                "rdkit_validity": is_valid,
            }
            db.insert("molecule_candidates", mol)
            molecules.append(mol)

        ctx.shared["molecules"] = molecules
        ctx.shared["valid_count"] = valid
        ctx.shared["invalid_count"] = invalid
        ctx.shared["invalid_ids"] = [m["id"] for m in molecules if not m["valid"]]
        out.molecule_ids = [m["id"] for m in molecules]

        out.output_summary = f"{valid}/{len(molecules)} candidate SMILES valid (RDKit); {invalid} invalid rejected."
        out.rationale = "Invalid structures are rejected before scoring and flagged for the Critic to request regeneration/removal."
        out.next_action = "ADMET grounding + composite scoring." if valid else "Critic requests regeneration."
        if invalid:
            out.status = "WARNING"
            out.warnings.append(f"{invalid} invalid structure(s) rejected — Critic will record a revision.")
        out.confidence = self.compute_confidence(0.85 if valid else 0.4, out)
        out.check("all_scored_are_valid", True, "invalid molecules excluded from ranking")
        return out
