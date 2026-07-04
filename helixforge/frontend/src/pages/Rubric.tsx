import { Icon } from '@/components/Icon'
import { Badge, PageHeader, Panel } from '@/components/ui'

type Readiness = 'Strong' | 'Partial' | 'Needs work'
const TONE: Record<Readiness, string> = { Strong: 'green', Partial: 'amber', 'Needs work': 'red' }

interface Row { criterion: string; readiness: Readiness; evidence: string }
interface Section { title: string; subtitle: string; rows: Row[] }

const PRELIM: Section = {
  title: '예선 평가 대응', subtitle: 'Preliminary evaluation alignment',
  rows: [
    { criterion: '필요성과 배경 (Necessity & background)', readiness: 'Strong', evidence: 'Clear NSCLC/EGFR problem; fragmented early-discovery pain points documented across Overview and reports.' },
    { criterion: '에이전트 설계 독창성 (Agent design originality)', readiness: 'Strong', evidence: '17-agent DAG with a Critic loop, six error-injection self-correction demos, and observable trace.' },
    { criterion: '기술적 실현 가능성 (Technical feasibility)', readiness: 'Strong', evidence: 'Real PubMed/ChEMBL/ClinicalTrials/RDKit/TDC; Vina/REINVENT4 adapters; Dockerized backend + frontend.' },
    { criterion: '평가 적절성 (Evaluation appropriateness)', readiness: 'Strong', evidence: 'Evaluation Bench with retrospective rediscovery, molecule validity, citation verification, self-correction metrics.' },
    { criterion: '비즈니스·사회적 가치 (Business/social value)', readiness: 'Partial', evidence: 'Impact page models time/cost reduction; conservative ranges, not field-validated.' },
    { criterion: '연구 윤리·완성도 (Research ethics & completeness)', readiness: 'Strong', evidence: 'Source labeling, audit log, safety gate, no-synthesis-route policy, human-responsibility statement.' },
  ],
}
const FINAL: Section = {
  title: '본선 평가 대응', subtitle: 'Final evaluation alignment',
  rows: [
    { criterion: '과학적 타당성·혁신성 (Scientific validity & innovation)', readiness: 'Strong', evidence: 'Evidence-grounded hypotheses, ChEMBL-sourced RDKit-validated candidates, transparent scoring, uncertainty.' },
    { criterion: '에이전트 자율성·지능 (Agent autonomy & intelligence)', readiness: 'Strong', evidence: 'Autonomous stage decomposition, critic-driven revision, error-injection self-correction (rate 1.0 in demo).' },
    { criterion: '도구 활용·통합 (Tool integration)', readiness: 'Strong', evidence: 'Live health matrix + per-tool-call ToolRun/audit with honest SourceType; missing tools never faked.' },
    { criterion: '리소스 효율성 (Resource efficiency)', readiness: 'Partial', evidence: 'Local deterministic tools + public APIs; resource metrics tracked; no LLM token cost. Router distillation planned.' },
    { criterion: '시연·완성도 (Demonstration completeness)', readiness: 'Strong', evidence: 'Agent Cockpit, Demo Lab, Presentation Mode, KO judge report, JSON export bundle.' },
  ],
}

function SectionCard({ s }: { s: Section }) {
  return (
    <Panel>
      <div className="mb-3">
        <div className="text-base font-semibold text-white">{s.title}</div>
        <div className="text-xs text-slate-500">{s.subtitle}</div>
      </div>
      <div className="space-y-2">
        {s.rows.map((r) => (
          <div key={r.criterion} className="rounded-lg border border-line bg-bg-soft/40 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="text-sm font-medium text-slate-100">{r.criterion}</div>
              <Badge tone={TONE[r.readiness]}>{r.readiness}</Badge>
            </div>
            <div className="mt-1 text-[11px] text-slate-400">{r.evidence}</div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

export function Rubric() {
  const all = [...PRELIM.rows, ...FINAL.rows]
  const strong = all.filter((r) => r.readiness === 'Strong').length
  return (
    <div>
      <PageHeader
        icon={<Icon name="Award" size={22} />}
        title="Rubric Alignment"
        subtitle="How HelixForge maps to the competition scoring criteria — a judge-facing 'why this wins' view with honest readiness badges."
        actions={<Badge tone="green">{strong}/{all.length} Strong</Badge>}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard s={PRELIM} />
        <SectionCard s={FINAL} />
      </div>
      <div className="mt-4 rounded-lg border border-line bg-bg-soft/40 p-3 text-xs text-slate-400">
        Readiness is self-assessed and deliberately honest: <span className="text-helix-amber">Partial</span> items (business validation, resource-router distillation) are on the roadmap and labeled as such rather than overclaimed.
      </div>
    </div>
  )
}
