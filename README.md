# HelixForge AI

**An agentic AI operating system for evidence-grounded target discovery, molecule optimization, safety screening, and clinical/regulatory strategy.**

Built for the 4th JUMP AI / AI Drug Discovery Competition — **Field 4** (integrated multi-agent system combining autonomous hypothesis generation, tool-based molecule optimization, safety/toxicity screening, and regulatory/clinical design support).

HelixForge AI is **not a chatbot**. It is a multi-agent, tool-using, evidence-grounded, auditable, safety-gated, end-to-end drug-discovery **decision-support** platform.

---

## Quick start

```bash
npm install
npm run dev        # http://localhost:5173
# production
npm run build
npm run preview    # http://localhost:4173
```

The app is **fully usable immediately** with no API keys — everything runs in deterministic **Demo Mode**. A rich seeded demo project (*NSCLC EGFR Retrospective Discovery Demo*) is loaded on first launch.

> On the Overview page, click **Run Full Demo Workflow** to watch 17 agents decompose the goal, call tools, validate outputs, self-correct injected errors, block unsafe candidates, and generate an auditable report.

---

## What it demonstrates

1. **Autonomous task decomposition** — Orchestrator builds a 16-stage DAG.
2. **Multi-agent collaboration** — 17 specialized agents (evidence, targets, molecules, ADMET, safety, clinical, regulatory, critic, reporting…).
3. **External scientific tool integration** — adapter interfaces for RDKit, TDC, REINVENT4, docking, literature, ClinicalTrials.gov, FDA/MFDS RAG, with graceful Demo fallback.
4. **Molecule validation & optimization loop** — SMILES validity gate, multi-objective scoring, regeneration on failure.
5. **Safety / ethics gate** — hazardous & dual-use screening, fabricated-citation rejection, **no synthesis routes**.
6. **Clinical/regulatory reasoning** — high-level TPP, trial design, endpoint & biomarker strategy, FDA/MFDS checklist.
7. **Evaluation metrics** — rediscovery, generation, ADMET, docking, agent, and safety benchmark modules.
8. **Resource/cost tracking** — token, latency, and cost ledger.
9. **Transparent observable audit trail** — every agent/tool/validation event logged (no hidden chain-of-thought).
10. **Exportable competition-ready report** — Markdown + JSON + browser PDF.

---

## Modes

- **Demo Mode** — no keys, deterministic simulated tools, all outputs labeled *Demo Simulation*.
- **Real Tool Mode** — adapter interfaces; unconfigured tools fall back to Demo and are labeled *Fallback*. A missing tool is **never** presented as used.

Toggle in the header or in **Settings**.

---

## Safety & honesty boundaries

This system provides high-level drug-discovery decision support only. It does **not** produce synthesis recipes, wet-lab protocols, reaction conditions, dosage/medical advice, or toxicity-enhancement guidance. Fabricated citations are rejected. Every clinical/regulatory output and report includes:

> *This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.*

---

## Tech stack

React 18 · TypeScript · Vite · Tailwind CSS · Zustand (localStorage persistence) · Recharts · lucide-react · React Router (hash).

## Architecture

```
src/
  components/   ui.tsx (design system), Layout, Icon, workflow.tsx (DAG/agent/audit)
  pages/        Overview, Projects, NewProject, Cockpit, EvidenceGraph, Targets,
                MoleculeLab, SafetyGate, Clinical, Evaluation, Training, ToolRegistry,
                Reports, Settings
  lib/          constants, scoring, safety, adapters, workflowEngine, reportTemplates,
                business, i18n
  data/         seedData (NSCLC EGFR demo package)
  store/        useAppStore (state machine + playback + persistence)
  types.ts      full data model
```

All scientific results are labeled **Real Tool Output**, **Demo Simulation**, or **Human-entered**. Demo values are never presented as real database or wet-lab results.
