import * as Lucide from 'lucide-react'
import type { LucideProps } from 'lucide-react'

// Resolve a lucide icon by name at runtime so constants/data can reference
// icons by string. Falls back to a neutral dot if the name is unknown.
export function Icon({ name, ...props }: { name: string } & LucideProps) {
  const Cmp = (Lucide as unknown as Record<string, React.ComponentType<LucideProps>>)[name] ?? Lucide.Circle
  return <Cmp {...props} />
}
