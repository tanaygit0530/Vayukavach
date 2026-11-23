import clsx from 'clsx'
import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
  /** Dashed border marks a card whose numbers are estimates. */
  estimated?: boolean
  as?: 'section' | 'div' | 'article'
}

export function Card({ title, subtitle, action, children, className, estimated, as = 'section' }: CardProps) {
  const Tag = as
  return (
    <Tag
      className={clsx(
        'glass-card p-5',
        estimated && 'border-2 border-dashed border-ink-muted/40',
        className,
      )}
      aria-label={title}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-[17px] font-medium leading-tight">{title}</h2>}
            {subtitle && <p className="mt-1 text-[13px] text-ink-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </Tag>
  )
}
