import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  Toggle,
  Disclaimer,
  KeyVal,
  PageHeader,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { HUMAN_RESPONSIBILITY_STATEMENT, DEMO_LABEL } from '@/lib/constants'
import type { DiscoveryGoal, Modality, AppMode } from '@/types'

// ---------------------------------------------------------------------------
// Wizard step metadata
// ---------------------------------------------------------------------------
const STEPS = [
  { id: 'problem', label: 'Problem', ko: '문제 정의', icon: 'Target' },
  { id: 'scientific', label: 'Constraints', ko: '과학적 제약', icon: 'FlaskConical' },
  { id: 'safety', label: 'Safety', ko: '안전 제약', icon: 'ShieldCheck' },
  { id: 'evaluation', label: 'Evaluation', ko: '평가 계획', icon: 'Gauge' },
  { id: 'launch', label: 'Launch', ko: '실행', icon: 'Rocket' },
] as const

const GOAL_OPTIONS: { value: DiscoveryGoal; label: string; desc: string }[] = [
  { value: 'target_discovery', label: 'Target Discovery', desc: '질환에서 새로운 표적을 발굴' },
  { value: 'repurposing', label: 'Drug Repurposing', desc: '기존 약물의 신규 적응증 탐색' },
  { value: 'de_novo', label: 'De Novo Design', desc: '제약 조건 하 신규 분자 설계' },
  { value: 'optimization', label: 'Lead Optimization', desc: '리드 후보 다목적 최적화' },
  { value: 'clinical_strategy', label: 'Clinical Strategy', desc: '고수준 임상 개발 전략 수립' },
  { value: 'full_pipeline', label: 'Full Pipeline', desc: '근거→표적→분자→안전→임상 전주기' },
]

const MODALITY_OPTIONS: { value: Modality; label: string }[] = [
  { value: 'small_molecule', label: 'Small Molecule' },
  { value: 'biologic', label: 'Biologic' },
  { value: 'repurposing', label: 'Repurposing' },
  { value: 'any', label: 'Any modality' },
]

interface FormState {
  name: string
  disease: string
  indication: string
  patientPopulation: string
  unmetNeed: string
  discoveryGoal: DiscoveryGoal
  mode: AppMode
  knownTargets: string
  excludedTargets: string
  mechanismPreferences: string
  biomarkerRequirements: string
  modality: Modality
  excludeControlled: boolean
  excludeHighToxicityOptimization: boolean
  noSynthesisRecipe: boolean
  humanReviewRequired: boolean
  retrospectiveRediscovery: boolean
  tdcAdmet: boolean
  dockingEnrichment: boolean
  citationVerification: boolean
  selfCorrection: boolean
  costLatency: boolean
}

const INITIAL: FormState = {
  name: 'EGFR-driven NSCLC — Novel Target Program',
  disease: 'Non-small cell lung cancer',
  indication: 'EGFR-mutant advanced NSCLC with acquired TKI resistance',
  patientPopulation: 'Adults with EGFR-mutant metastatic NSCLC progressing on prior EGFR tyrosine-kinase inhibitors',
  unmetNeed:
    'Acquired resistance (e.g., C797S, MET amplification) after later-generation EGFR TKIs leaves patients with limited durable options and poor CNS coverage.',
  discoveryGoal: 'full_pipeline',
  mode: 'demo',
  knownTargets: 'EGFR',
  excludedTargets: '',
  mechanismPreferences: 'Mutant-selective inhibition, allosteric mechanism, CNS penetrant',
  biomarkerRequirements: 'EGFR mutation status, ctDNA clearance',
  modality: 'small_molecule',
  excludeControlled: true,
  excludeHighToxicityOptimization: true,
  noSynthesisRecipe: true,
  humanReviewRequired: true,
  retrospectiveRediscovery: true,
  tdcAdmet: true,
  dockingEnrichment: true,
  citationVerification: true,
  selfCorrection: true,
  costLatency: true,
}

function toArr(s: string): string[] {
  return s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
}

// Small labeled field wrapper -------------------------------------------------
function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <div className="mt-1 text-[11px] text-slate-500">{hint}</div>}
    </div>
  )
}

const SAFETY_TOGGLES: { key: keyof FormState; label: string; desc: string }[] = [
  { key: 'excludeControlled', label: 'Exclude controlled / hazardous chemistry', desc: '규제·위험 물질 계열을 생성 공간에서 제외' },
  { key: 'excludeHighToxicityOptimization', label: 'Never optimize toward toxicity', desc: '독성 강화 방향 최적화를 금지' },
  { key: 'noSynthesisRecipe', label: 'No actionable synthesis routes', desc: '실행 가능한 합성 경로·시약·조건 미표시' },
  { key: 'humanReviewRequired', label: 'Human expert review required', desc: '모든 결과에 인간 전문가 검토를 의무화' },
]

const EVAL_TOGGLES: { key: keyof FormState; label: string; desc: string }[] = [
  { key: 'retrospectiveRediscovery', label: 'Retrospective rediscovery', desc: '알려진 약물 재발견 벤치마크' },
  { key: 'tdcAdmet', label: 'TDC ADMET benchmarks', desc: 'Therapeutics Data Commons 태스크' },
  { key: 'dockingEnrichment', label: 'Docking enrichment', desc: '결합 스코어 enrichment 평가' },
  { key: 'citationVerification', label: 'Citation verification', desc: '인용 식별자 교차검증' },
  { key: 'selfCorrection', label: 'Self-correction loop', desc: '오류 주입→탐지→수정 검증' },
  { key: 'costLatency', label: 'Cost & latency tracking', desc: '토큰·비용·지연 시간 계측' },
]

export function NewProject() {
  const navigate = useNavigate()
  const createProject = useAppStore((s) => s.createProject)
  const startWorkflow = useAppStore((s) => s.startWorkflow)

  const [step, setStep] = React.useState(0)
  const [form, setForm] = React.useState<FormState>(INITIAL)

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const goalMeta = GOAL_OPTIONS.find((g) => g.value === form.discoveryGoal)!
  const step0Valid = form.name.trim().length > 0 && form.disease.trim().length > 0

  const launch = () => {
    const id = createProject({
      name: form.name.trim() || 'Untitled Project',
      disease: form.disease.trim(),
      indication: form.indication.trim(),
      patientPopulation: form.patientPopulation.trim(),
      unmetNeed: form.unmetNeed.trim(),
      discoveryGoal: form.discoveryGoal,
      mode: form.mode,
      scientificConstraints: {
        knownTargets: toArr(form.knownTargets),
        excludedTargets: toArr(form.excludedTargets),
        mechanismPreferences: toArr(form.mechanismPreferences),
        biomarkerRequirements: toArr(form.biomarkerRequirements),
        modality: form.modality,
      },
      safetyConstraints: {
        excludeControlled: form.excludeControlled,
        excludeHighToxicityOptimization: form.excludeHighToxicityOptimization,
        noSynthesisRecipe: form.noSynthesisRecipe,
        humanReviewRequired: form.humanReviewRequired,
      },
      evaluationPlan: {
        retrospectiveRediscovery: form.retrospectiveRediscovery,
        tdcAdmet: form.tdcAdmet,
        dockingEnrichment: form.dockingEnrichment,
        citationVerification: form.citationVerification,
        selfCorrection: form.selfCorrection,
        costLatency: form.costLatency,
      },
    })
    startWorkflow(id)
    navigate('/cockpit')
  }

  const evalCount = EVAL_TOGGLES.filter((t) => form[t.key]).length
  const safetyCount = SAFETY_TOGGLES.filter((t) => form[t.key]).length

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader
        title="Create New Project · 새 프로젝트"
        subtitle="Define a drug-discovery objective, then let the multi-agent workflow decompose it into an auditable pipeline. 목표를 정의하면 다중 에이전트 워크플로우가 감사 가능한 파이프라인으로 분해합니다."
        icon="FolderPlus"
        actions={<Badge tone="cyan" icon="FlaskConical">{DEMO_LABEL}</Badge>}
      />

      {/* Step indicator */}
      <Panel className="p-4">
        <div className="flex items-center">
          {STEPS.map((s, i) => {
            const state = i < step ? 'done' : i === step ? 'active' : 'todo'
            return (
              <React.Fragment key={s.id}>
                <button
                  type="button"
                  onClick={() => i <= step && setStep(i)}
                  disabled={i > step}
                  className={`flex min-w-0 flex-col items-center gap-1.5 text-center ${
                    i <= step ? 'cursor-pointer' : 'cursor-default'
                  }`}
                >
                  <span
                    className={`grid h-9 w-9 place-items-center rounded-full border transition-colors ${
                      state === 'done'
                        ? 'border-transparent bg-brand-500 text-white'
                        : state === 'active'
                          ? 'border-helix-cyan bg-helix-cyan/15 text-helix-cyan'
                          : 'border-line bg-bg-soft text-slate-500'
                    }`}
                  >
                    <Icon name={state === 'done' ? 'Check' : s.icon} size={16} />
                  </span>
                  <div className="leading-tight">
                    <div
                      className={`text-[11px] font-medium ${
                        state === 'todo' ? 'text-slate-500' : 'text-slate-200'
                      }`}
                    >
                      {s.label}
                    </div>
                    <div className="hidden text-[10px] text-slate-500 sm:block">{s.ko}</div>
                  </div>
                </button>
                {i < STEPS.length - 1 && (
                  <div
                    className={`mx-1 mb-6 h-px flex-1 ${i < step ? 'bg-brand-500/60' : 'bg-line'}`}
                  />
                )}
              </React.Fragment>
            )
          })}
        </div>
      </Panel>

      {/* Step body */}
      <Panel className="p-5">
        {step === 0 && (
          <div className="space-y-4">
            <SectionTitle icon="Target" right={<span className="text-xs text-slate-500">Step 1 / 5</span>}>
              문제 정의 · Problem Definition
            </SectionTitle>
            <Field label="Project name · 프로젝트 이름">
              <input
                className="input"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="e.g., EGFR-driven NSCLC — Novel Target Program"
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Disease · 질환">
                <input className="input" value={form.disease} onChange={(e) => set('disease', e.target.value)} />
              </Field>
              <Field label="Indication · 적응증">
                <input className="input" value={form.indication} onChange={(e) => set('indication', e.target.value)} />
              </Field>
            </div>
            <Field label="Patient population · 환자군">
              <input
                className="input"
                value={form.patientPopulation}
                onChange={(e) => set('patientPopulation', e.target.value)}
              />
            </Field>
            <Field label="Unmet need · 미충족 수요">
              <textarea
                className="input min-h-[80px] resize-y"
                value={form.unmetNeed}
                onChange={(e) => set('unmetNeed', e.target.value)}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Discovery goal · 발굴 목표" hint={goalMeta.desc}>
                <select
                  className="input"
                  value={form.discoveryGoal}
                  onChange={(e) => set('discoveryGoal', e.target.value as DiscoveryGoal)}
                >
                  {GOAL_OPTIONS.map((g) => (
                    <option key={g.value} value={g.value}>
                      {g.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Run mode · 실행 모드" hint="Real 모드는 연결된 어댑터가 없으면 Demo Fallback으로 동작합니다.">
                <div className="grid grid-cols-2 gap-2">
                  {(['demo', 'real'] as AppMode[]).map((m) => {
                    const active = form.mode === m
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => set('mode', m)}
                        className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                          active
                            ? 'border-helix-cyan bg-helix-cyan/10 text-white'
                            : 'border-line bg-bg-soft text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Icon
                          name={active ? 'CircleDot' : 'Circle'}
                          size={15}
                          className={active ? 'text-helix-cyan' : 'text-slate-600'}
                        />
                        {m === 'demo' ? 'Demo' : 'Real Tool'}
                      </button>
                    )
                  })}
                </div>
              </Field>
            </div>
            {!step0Valid && (
              <div className="text-[11px] text-helix-amber">
                Project name and disease are required to continue.
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <SectionTitle icon="FlaskConical" right={<span className="text-xs text-slate-500">Step 2 / 5</span>}>
              과학적 제약 · Scientific Constraints
            </SectionTitle>
            <p className="text-xs text-slate-500">
              Comma-separated lists guide the Target Scout and Molecular Design agents. Leave blank to let the system explore
              freely. 쉼표로 구분해 입력하세요.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Known targets · 알려진 표적" hint="e.g., EGFR, MET">
                <input className="input" value={form.knownTargets} onChange={(e) => set('knownTargets', e.target.value)} />
              </Field>
              <Field label="Excluded targets · 제외 표적" hint="탐색에서 배제할 표적">
                <input
                  className="input"
                  value={form.excludedTargets}
                  onChange={(e) => set('excludedTargets', e.target.value)}
                />
              </Field>
            </div>
            <Field label="Mechanism preferences · 선호 기전" hint="e.g., allosteric, mutant-selective">
              <input
                className="input"
                value={form.mechanismPreferences}
                onChange={(e) => set('mechanismPreferences', e.target.value)}
              />
            </Field>
            <Field label="Biomarker requirements · 바이오마커 요건" hint="환자 선별/반응 예측 바이오마커">
              <input
                className="input"
                value={form.biomarkerRequirements}
                onChange={(e) => set('biomarkerRequirements', e.target.value)}
              />
            </Field>
            <Field label="Modality · 모달리티">
              <select
                className="input"
                value={form.modality}
                onChange={(e) => set('modality', e.target.value as Modality)}
              >
                {MODALITY_OPTIONS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <SectionTitle icon="ShieldCheck" right={<Badge tone="green" icon="Lock">Enforced</Badge>}>
              안전 제약 · Safety Constraints
            </SectionTitle>
            <Disclaimer tone="green">
              These guardrails are enforced by the Safety Auditor throughout the workflow. They are enabled by default and
              cannot be silently bypassed — disabling one is logged in the audit trail. 안전 가드레일은 기본 활성화되며 감사
              로그에 기록됩니다.
            </Disclaimer>
            <div className="space-y-3">
              {SAFETY_TOGGLES.map((t) => (
                <div key={t.key} className="rounded-lg border border-line bg-bg-raised/40 p-3">
                  <Toggle
                    checked={form[t.key] as boolean}
                    onChange={(v) => set(t.key, v as never)}
                    label={t.label}
                    desc={t.desc}
                  />
                </div>
              ))}
            </div>
            <div className="text-[11px] text-slate-500">
              {safetyCount} / 4 guardrails enabled. Actionable synthesis routes are never displayed regardless of settings.
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <SectionTitle icon="Gauge" right={<span className="text-xs text-slate-500">Step 4 / 5</span>}>
              평가 계획 · Evaluation Plan
            </SectionTitle>
            <p className="text-xs text-slate-500">
              Select which benchmark modules the Evaluation Harness Agent should run after the pipeline completes. 완료 후
              실행할 벤치마크 모듈을 선택하세요.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {EVAL_TOGGLES.map((t) => (
                <div key={t.key} className="rounded-lg border border-line bg-bg-raised/40 p-3">
                  <Toggle
                    checked={form[t.key] as boolean}
                    onChange={(v) => set(t.key, v as never)}
                    label={t.label}
                    desc={t.desc}
                  />
                </div>
              ))}
            </div>
            <div className="text-[11px] text-slate-500">{evalCount} / 6 benchmark modules selected.</div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <SectionTitle icon="Rocket" right={<span className="text-xs text-slate-500">Step 5 / 5</span>}>
              실행 · Launch Review
            </SectionTitle>

            <div className="grid gap-4 md:grid-cols-2">
              <Panel raised className="p-4">
                <SectionTitle icon="Target">Problem</SectionTitle>
                <KeyVal k="Name" v={form.name || '—'} />
                <KeyVal k="Disease" v={form.disease || '—'} />
                <KeyVal k="Indication" v={form.indication || '—'} />
                <KeyVal k="Goal" v={goalMeta.label} />
                <KeyVal
                  k="Mode"
                  v={<Badge tone={form.mode === 'demo' ? 'cyan' : 'green'}>{form.mode === 'demo' ? 'Demo' : 'Real Tool'}</Badge>}
                />
              </Panel>
              <Panel raised className="p-4">
                <SectionTitle icon="FlaskConical">Constraints</SectionTitle>
                <KeyVal k="Modality" v={MODALITY_OPTIONS.find((m) => m.value === form.modality)?.label ?? form.modality} />
                <KeyVal k="Known targets" v={toArr(form.knownTargets).join(', ') || '—'} mono />
                <KeyVal k="Excluded" v={toArr(form.excludedTargets).join(', ') || '—'} mono />
                <KeyVal k="Mechanisms" v={toArr(form.mechanismPreferences).length || '—'} />
                <KeyVal k="Biomarkers" v={toArr(form.biomarkerRequirements).length || '—'} />
              </Panel>
              <Panel raised className="p-4">
                <SectionTitle icon="ShieldCheck">Safety guardrails</SectionTitle>
                <div className="flex flex-wrap gap-1.5">
                  {SAFETY_TOGGLES.map((t) => (
                    <Badge key={t.key} tone={form[t.key] ? 'green' : 'slate'} icon={form[t.key] ? 'ShieldCheck' : 'ShieldOff'}>
                      {t.label.split(' ').slice(0, 2).join(' ')}
                    </Badge>
                  ))}
                </div>
                <div className="mt-2 text-[11px] text-slate-500">{safetyCount} / 4 enforced</div>
              </Panel>
              <Panel raised className="p-4">
                <SectionTitle icon="Gauge">Evaluation modules</SectionTitle>
                <div className="flex flex-wrap gap-1.5">
                  {EVAL_TOGGLES.filter((t) => form[t.key]).map((t) => (
                    <Badge key={t.key} tone="cyan" icon="Check">
                      {t.label}
                    </Badge>
                  ))}
                  {evalCount === 0 && <span className="text-xs text-slate-500">None selected</span>}
                </div>
                <div className="mt-2 text-[11px] text-slate-500">{evalCount} / 6 modules</div>
              </Panel>
            </div>

            <Disclaimer tone="amber">{HUMAN_RESPONSIBILITY_STATEMENT}</Disclaimer>
            <div className="text-[11px] text-slate-500">
              On launch, a scientific dataset is seeded as a {DEMO_LABEL.replace(' — not a real database/tool result.', '')} and the
              multi-agent workflow begins in the Agent Cockpit.
            </div>
          </div>
        )}
      </Panel>

      {/* Footer nav */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          icon="ArrowLeft"
          onClick={() => (step === 0 ? navigate('/projects') : setStep((s) => s - 1))}
        >
          {step === 0 ? 'Cancel' : 'Back'}
        </Button>
        {step < STEPS.length - 1 ? (
          <Button
            variant="primary"
            icon="ArrowRight"
            disabled={step === 0 && !step0Valid}
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
          >
            Next
          </Button>
        ) : (
          <Button variant="primary" icon="Play" onClick={launch}>
            Start Workflow
          </Button>
        )}
      </div>
    </div>
  )
}
