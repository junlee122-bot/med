import type { Language } from '@/types'

// Lightweight bilingual dictionary. Korean is the default UI language per spec;
// technical labels stay understandable in English via subtitles.
type Dict = Record<string, { ko: string; en: string }>

export const NAV: { key: string; path: string; ko: string; en: string; icon: string; group: string }[] = [
  { key: 'overview', path: '/', ko: '개요', en: 'Overview', icon: 'LayoutDashboard', group: 'main' },
  { key: 'projects', path: '/projects', ko: '프로젝트', en: 'Projects', icon: 'FolderKanban', group: 'main' },
  { key: 'cockpit', path: '/cockpit', ko: '에이전트 콕핏', en: 'Agent Cockpit', icon: 'Cpu', group: 'run' },
  { key: 'evidence', path: '/evidence', ko: '근거 그래프', en: 'Evidence Graph', icon: 'Share2', group: 'run' },
  { key: 'targets', path: '/targets', ko: '타깃 우선순위', en: 'Targets', icon: 'Crosshair', group: 'run' },
  { key: 'molecules', path: '/molecules', ko: '분자 최적화 랩', en: 'Molecule Lab', icon: 'Atom', group: 'run' },
  { key: 'safety', path: '/safety', ko: '안전·윤리 게이트', en: 'Safety Gate', icon: 'ShieldCheck', group: 'run' },
  { key: 'clinical', path: '/clinical', ko: '임상·규제 전략', en: 'Clinical & Regulatory', icon: 'Stethoscope', group: 'run' },
  { key: 'evaluation', path: '/evaluation', ko: '평가 벤치', en: 'Evaluation Bench', icon: 'Gauge', group: 'analysis' },
  { key: 'training', path: '/training', ko: '모델 트레이닝 스튜디오', en: 'Training Studio', icon: 'Boxes', group: 'analysis' },
  { key: 'tools', path: '/tools', ko: '툴 레지스트리', en: 'Tool Registry', icon: 'Plug', group: 'analysis' },
  { key: 'reports', path: '/reports', ko: '보고서', en: 'Reports', icon: 'FileText', group: 'analysis' },
  { key: 'settings', path: '/settings', ko: '설정', en: 'Settings', icon: 'Settings', group: 'system' },
]

export const NAV_GROUPS: { id: string; ko: string; en: string }[] = [
  { id: 'main', ko: '워크스페이스', en: 'Workspace' },
  { id: 'run', ko: '디스커버리 실행', en: 'Discovery Run' },
  { id: 'analysis', ko: '분석 & 확장', en: 'Analysis & Extension' },
  { id: 'system', ko: '시스템', en: 'System' },
]

const DICT: Dict = {
  appName: { ko: 'HelixForge AI', en: 'HelixForge AI' },
  tagline: {
    ko: '증거 기반 타깃 발굴·분자 최적화·안전성 스크리닝·임상/규제 전략을 위한 에이전트형 AI 운영체제',
    en: 'An agentic AI operating system for evidence-grounded target discovery, molecule optimization, safety screening, and clinical/regulatory strategy.',
  },
  runDemo: { ko: '전체 데모 워크플로우 실행', en: 'Run Full Demo Workflow' },
  newProject: { ko: '새 프로젝트 생성', en: 'Create New Project' },
  demoMode: { ko: '데모 모드', en: 'Demo Mode' },
  realMode: { ko: '실제 툴 모드', en: 'Real Tool Mode' },
  safetyBanner: {
    ko: '연구 의사결정 지원 전용 · 실험 프로토콜/합성 레시피/의료 자문을 제공하지 않습니다.',
    en: 'Research decision support only. No wet-lab protocol, no synthesis recipe, no medical advice.',
  },
  observableTrace: { ko: '관찰 가능한 에이전트 추적', en: 'Observable Agent Trace' },
}

let current: Language = 'ko'
export function setLang(l: Language) {
  current = l
}
export function t(key: string, lang?: Language): string {
  const l = lang ?? current
  return DICT[key]?.[l] ?? key
}

// Bilingual heading helper: returns { primary, secondary } based on language.
export function heading(ko: string, en: string, lang: Language) {
  return lang === 'ko' ? { primary: ko, secondary: en } : { primary: en, secondary: ko }
}
