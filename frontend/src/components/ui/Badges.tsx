import clsx from 'clsx'
import { Clock } from 'lucide-react'

import { updatedAgo } from '../../lib/format'

/** Dashed pill: the value is a model or filled estimate, not a station measurement. */
export function EstimatedBadge({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border border-dashed border-ink-muted px-2 py-0.5 text-[11px] font-medium text-ink-muted',
        className,
      )}
    >
      Estimated
    </span>
  )
}

export function MeasuredBadge({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border border-ink-muted/50 px-2 py-0.5 text-[11px] font-medium text-ink-muted',
        className,
      )}
    >
      Measured
    </span>
  )
}

/** Amber "Updated 3 h ago" when data is older than 2 hours (the API's `stale`). */
export function StaleBadge({
  updatedAt,
  stale,
  className,
}: {
  updatedAt: string | null
  stale: boolean
  className?: string
}) {
  if (!stale) return null
  const text = updatedAgo(updatedAt) ?? 'No recent update'
  return (
    <span
      role="status"
      className={clsx(
        'inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-stale',
        className,
      )}
    >
      <Clock aria-hidden className="h-3 w-3" />
      {text}
    </span>
  )
}

export function LabelBadge({ label }: { label: string | null }) {
  if (label === 'estimated') return <EstimatedBadge />
  if (label === 'measured') return <MeasuredBadge />
  return null
}
