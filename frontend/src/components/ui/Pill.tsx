import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Pill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        'glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[14px] font-medium',
        className,
      )}
    >
      {children}
    </span>
  )
}
