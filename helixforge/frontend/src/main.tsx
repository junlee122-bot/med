import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { Layout } from '@/components/Layout'
import { Spinner } from '@/components/ui'

const Overview = lazy(() => import('@/pages/Overview').then((m) => ({ default: m.Overview })))
const ToolRegistry = lazy(() => import('@/pages/ToolRegistry').then((m) => ({ default: m.ToolRegistry })))
const ComputeCenter = lazy(() => import('@/pages/ComputeCenter').then((m) => ({ default: m.ComputeCenter })))
const ModelLab = lazy(() => import('@/pages/ModelLab').then((m) => ({ default: m.ModelLab })))
const ActiveLearning = lazy(() => import('@/pages/ActiveLearning').then((m) => ({ default: m.ActiveLearning })))
const NewRun = lazy(() => import('@/pages/NewRun').then((m) => ({ default: m.NewRun })))
const Hybrid = lazy(() => import('@/pages/Hybrid').then((m) => ({ default: m.Hybrid })))
const LLMRouter = lazy(() => import('@/pages/LLMRouter').then((m) => ({ default: m.LLMRouter })))
const Rediscovery = lazy(() => import('@/pages/Rediscovery').then((m) => ({ default: m.Rediscovery })))
const OptimizationLoop = lazy(() => import('@/pages/OptimizationLoop').then((m) => ({ default: m.OptimizationLoop })))
const Cockpit = lazy(() => import('@/pages/Cockpit').then((m) => ({ default: m.Cockpit })))
const PeerReview = lazy(() => import('@/pages/PeerReview').then((m) => ({ default: m.PeerReview })))
const ProposalStudio = lazy(() => import('@/pages/ProposalStudio').then((m) => ({ default: m.ProposalStudio })))
const EvidenceGrading = lazy(() => import('@/pages/EvidenceGrading').then((m) => ({ default: m.EvidenceGrading })))
const MoleculeQA = lazy(() => import('@/pages/MoleculeQA').then((m) => ({ default: m.MoleculeQA })))
const ProfessionalReview = lazy(() => import('@/pages/ProfessionalReview').then((m) => ({ default: m.ProfessionalReview })))
const ExpertReview = lazy(() => import('@/pages/ExpertReview').then((m) => ({ default: m.ExpertReview })))
const ProfessionalDocs = lazy(() => import('@/pages/ProfessionalDocs').then((m) => ({ default: m.ProfessionalDocs })))
const DemoLab = lazy(() => import('@/pages/DemoLab').then((m) => ({ default: m.DemoLab })))
const Snapshots = lazy(() => import('@/pages/Snapshots').then((m) => ({ default: m.Snapshots })))
const ScenarioMatrix = lazy(() => import('@/pages/ScenarioMatrix').then((m) => ({ default: m.ScenarioMatrix })))
const AILedger = lazy(() => import('@/pages/AILedger').then((m) => ({ default: m.AILedger })))
const Release = lazy(() => import('@/pages/Release').then((m) => ({ default: m.Release })))
const Submission = lazy(() => import('@/pages/Submission').then((m) => ({ default: m.Submission })))
const EvidenceExplorer = lazy(() => import('@/pages/EvidenceExplorer').then((m) => ({ default: m.EvidenceExplorer })))
const Targets = lazy(() => import('@/pages/Targets').then((m) => ({ default: m.Targets })))
const Hypotheses = lazy(() => import('@/pages/Hypotheses').then((m) => ({ default: m.Hypotheses })))
const MoleculeLab = lazy(() => import('@/pages/MoleculeLab').then((m) => ({ default: m.MoleculeLab })))
const TDCBench = lazy(() => import('@/pages/TDCBench').then((m) => ({ default: m.TDCBench })))
const DockingLab = lazy(() => import('@/pages/DockingLab').then((m) => ({ default: m.DockingLab })))
const ReinventStudio = lazy(() => import('@/pages/ReinventStudio').then((m) => ({ default: m.ReinventStudio })))
const Clinical = lazy(() => import('@/pages/Clinical').then((m) => ({ default: m.Clinical })))
const SafetyGate = lazy(() => import('@/pages/SafetyGate').then((m) => ({ default: m.SafetyGate })))
const Evaluation = lazy(() => import('@/pages/Evaluation').then((m) => ({ default: m.Evaluation })))
const Impact = lazy(() => import('@/pages/Impact').then((m) => ({ default: m.Impact })))
const Rubric = lazy(() => import('@/pages/Rubric').then((m) => ({ default: m.Rubric })))
const Reports = lazy(() => import('@/pages/Reports').then((m) => ({ default: m.Reports })))
const Presentation = lazy(() => import('@/pages/Presentation').then((m) => ({ default: m.Presentation })))
const Settings = lazy(() => import('@/pages/Settings').then((m) => ({ default: m.Settings })))

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Layout>
        <Suspense fallback={<Spinner label="Loading page…" />}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/tools" element={<ToolRegistry />} />
          <Route path="/compute" element={<ComputeCenter />} />
          <Route path="/model-lab" element={<ModelLab />} />
          <Route path="/active-learning" element={<ActiveLearning />} />
          <Route path="/new-run" element={<NewRun />} />
          <Route path="/hybrid" element={<Hybrid />} />
          <Route path="/llm" element={<LLMRouter />} />
          <Route path="/rediscovery" element={<Rediscovery />} />
          <Route path="/optimization-loop" element={<OptimizationLoop />} />
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
        </Suspense>
      </Layout>
    </HashRouter>
  </React.StrictMode>,
)
