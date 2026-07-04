import * as Lucide from 'lucide-react'
import type { LucideProps } from 'lucide-react'

// Resolve a lucide icon by name with a safe fallback (never crashes on a typo).
export function Icon({ name, ...props }: { name: string } & LucideProps) {
  const C = (Lucide as any)[name] || Lucide.Circle
  return <C {...props} />
}
