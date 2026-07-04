import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Overview } from '@/pages/Overview'
import { Projects } from '@/pages/Projects'
import { NewProject } from '@/pages/NewProject'
import { Cockpit } from '@/pages/Cockpit'
import { EvidenceGraph } from '@/pages/EvidenceGraph'
import { Targets } from '@/pages/Targets'
import { MoleculeLab } from '@/pages/MoleculeLab'
import { SafetyGate } from '@/pages/SafetyGate'
import { Clinical } from '@/pages/Clinical'
import { Evaluation } from '@/pages/Evaluation'
import { Training } from '@/pages/Training'
import { ToolRegistry } from '@/pages/ToolRegistry'
import { Reports } from '@/pages/Reports'
import { Settings } from '@/pages/Settings'

export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/new" element={<NewProject />} />
          <Route path="/cockpit" element={<Cockpit />} />
          <Route path="/evidence" element={<EvidenceGraph />} />
          <Route path="/targets" element={<Targets />} />
          <Route path="/molecules" element={<MoleculeLab />} />
          <Route path="/safety" element={<SafetyGate />} />
          <Route path="/clinical" element={<Clinical />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/training" element={<Training />} />
          <Route path="/tools" element={<ToolRegistry />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </HashRouter>
  )
}
