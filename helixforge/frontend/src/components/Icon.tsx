import {
  Activity, AlertCircle, AlertTriangle, Archive, ArrowRight, Atom, Award,
  BarChart3, BookCheck, BookOpen, BookX, Boxes, Braces, BrainCircuit, Camera,
  Check, CheckCircle2, ChevronLeft, ChevronRight, Circle, ClipboardCheck,
  ClipboardCopy, Copy, Cpu, Crosshair, DatabaseZap, Download, ExternalLink, FileCog,
  FileEdit, FileSearch, FileStack, FileText, FlaskConical, Gauge, GitBranch,
  GitCompare, GitCompareArrows, Grid3x3, Info, KeyRound, LayoutDashboard,
  Lightbulb, ListPlus, Loader2, Magnet, MessageSquareWarning, Microscope,
  Minus, MinusCircle, Package, Play, Plug, PlugZap, Plus, Presentation,
  Printer, Radar, RefreshCw, Rocket, RotateCcw, Rows3, Save, Scale,
  ScanSearch, ScrollText, Search, Settings, ShieldAlert, ShieldCheck, ShieldX,
  Sparkles, Stethoscope, Target, Timer, Trash2, TrendingUp, UserCheck, Users,
  Wand2, Workflow, X, XCircle, Zap,
  type LucideIcon,
  type LucideProps,
} from 'lucide-react'

const ICONS = {
  Activity, AlertCircle, AlertTriangle, Archive, ArrowRight, Atom, Award,
  BarChart3, BookCheck, BookOpen, BookX, Boxes, Braces, BrainCircuit, Camera,
  Check, CheckCircle2, ChevronLeft, ChevronRight, Circle, ClipboardCheck,
  ClipboardCopy, Copy, Cpu, Crosshair, DatabaseZap, Download, ExternalLink, FileCog,
  FileEdit, FileSearch, FileStack, FileText, FlaskConical, Gauge, GitBranch,
  GitCompare, GitCompareArrows, Grid3x3, Info, KeyRound, LayoutDashboard,
  Lightbulb, ListPlus, Loader2, Magnet, MessageSquareWarning, Microscope,
  Minus, MinusCircle, Package, Play, Plug, PlugZap, Plus, Presentation,
  Printer, Radar, RefreshCw, Rocket, RotateCcw, Rows3, Save, Scale,
  ScanSearch, ScrollText, Search, Settings, ShieldAlert, ShieldCheck, ShieldX,
  Sparkles, Stethoscope, Target, Timer, Trash2, TrendingUp, UserCheck, Users,
  Wand2, Workflow, X, XCircle, Zap,
} satisfies Record<string, LucideIcon>

// Resolve a lucide icon by name with a safe fallback (never crashes on a typo).
export function Icon({ name, ...props }: { name: string } & LucideProps) {
  const C = ICONS[name as keyof typeof ICONS] || Circle
  return <C {...props} />
}
