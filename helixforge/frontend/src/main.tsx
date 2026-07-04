import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { Layout } from '@/components/Layout'
import { Overview } from '@/pages/Overview'
import { ToolRegistry } from '@/pages/ToolRegistry'
import { Cockpit } from '@/pages/Cockpit'
import { EvidenceExplorer } from '@/pages/EvidenceExplorer'
import { MoleculeLab } from '@/pages/MoleculeLab'
import { TDCBench } from '@/pages/TDCBench'
import { DockingLab } from '@/pages/DockingLab'
import { ReinventStudio } from '@/pages/ReinventStudio'
import { SafetyGate } from '@/pages/SafetyGate'
import { Reports } from '@/pages/Reports'
import { Settings } from '@/pages/Settings'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/tools" element={<ToolRegistry />} />
          <Route path="/cockpit" element={<Cockpit />} />
          <Route path="/evidence" element={<EvidenceExplorer />} />
          <Route path="/molecules" element={<MoleculeLab />} />
          <Route path="/tdc" element={<TDCBench />} />
          <Route path="/docking" element={<DockingLab />} />
          <Route path="/reinvent" element={<ReinventStudio />} />
          <Route path="/safety" element={<SafetyGate />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </HashRouter>
  </React.StrictMode>,
)
