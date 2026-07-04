import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { Layout } from '@/components/Layout'
import { Overview } from '@/pages/Overview'
import { ToolRegistry } from '@/pages/ToolRegistry'
import { NewRun } from '@/pages/NewRun'
import { Cockpit } from '@/pages/Cockpit'
import { PeerReview } from '@/pages/PeerReview'
import { ProposalStudio } from '@/pages/ProposalStudio'
import { EvidenceGrading } from '@/pages/EvidenceGrading'
import { MoleculeQA } from '@/pages/MoleculeQA'
import { ProfessionalReview } from '@/pages/ProfessionalReview'
import { ExpertReview } from '@/pages/ExpertReview'
import { ProfessionalDocs } from '@/pages/ProfessionalDocs'
import { DemoLab } from '@/pages/DemoLab'
import { Snapshots } from '@/pages/Snapshots'
import { ScenarioMatrix } from '@/pages/ScenarioMatrix'
import { AILedger } from '@/pages/AILedger'
import { Release } from '@/pages/Release'
import { Submission } from '@/pages/Submission'
import { EvidenceExplorer } from '@/pages/EvidenceExplorer'
import { Targets } from '@/pages/Targets'
import { Hypotheses } from '@/pages/Hypotheses'
import { MoleculeLab } from '@/pages/MoleculeLab'
import { TDCBench } from '@/pages/TDCBench'
import { DockingLab } from '@/pages/DockingLab'
import { ReinventStudio } from '@/pages/ReinventStudio'
import { Clinical } from '@/pages/Clinical'
import { SafetyGate } from '@/pages/SafetyGate'
import { Evaluation } from '@/pages/Evaluation'
import { Impact } from '@/pages/Impact'
import { Rubric } from '@/pages/Rubric'
import { Reports } from '@/pages/Reports'
import { Presentation } from '@/pages/Presentation'
import { Settings } from '@/pages/Settings'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/tools" element={<ToolRegistry />} />
          <Route path="/new-run" element={<NewRun />} />
          <Route path="/cockpit" element={<Cockpit />} />
          <Route path="/peer-review" element={<PeerReview />} />
          <Route path="/proposal-studio" element={<ProposalStudio />} />
          <Route path="/professional-docs" element={<ProfessionalDocs />} />
          <Route path="/demo-lab" element={<DemoLab />} />
          <Route path="/snapshots" element={<Snapshots />} />
          <Route path="/scenarios" element={<ScenarioMatrix />} />
          <Route path="/ai-ledger" element={<AILedger />} />
          <Route path="/release" element={<Release />} />
          <Route path="/submission" element={<Submission />} />
          <Route path="/evidence" element={<EvidenceExplorer />} />
          <Route path="/evidence-grading" element={<EvidenceGrading />} />
          <Route path="/molecule-qa" element={<MoleculeQA />} />
          <Route path="/professional-review" element={<ProfessionalReview />} />
          <Route path="/expert-review" element={<ExpertReview />} />
          <Route path="/targets" element={<Targets />} />
          <Route path="/hypotheses" element={<Hypotheses />} />
          <Route path="/molecules" element={<MoleculeLab />} />
          <Route path="/tdc" element={<TDCBench />} />
          <Route path="/docking" element={<DockingLab />} />
          <Route path="/reinvent" element={<ReinventStudio />} />
          <Route path="/clinical" element={<Clinical />} />
          <Route path="/safety" element={<SafetyGate />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/impact" element={<Impact />} />
          <Route path="/rubric" element={<Rubric />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/presentation" element={<Presentation />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </HashRouter>
  </React.StrictMode>,
)
