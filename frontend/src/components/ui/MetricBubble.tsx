import clsx from 'clsx'
import type { ReactNode } from 'react'

import { Skeleton } from './Skeleton'

interface MetricBubbleProps {
  icon?: ReactNode
  value: string | null
  unit?: string
  label: string
  /** Extra line under the label, e.g. a category or a band. */
  detail?: ReactNode
  size?: number
  loading?: boolean
  /** The request failed: say so, rather than implying there is no reading. */
  error?: boolean
  estimated?: boolean
  stale?: boolean
  /** Ring colour, e.g. an AQI category colour. */
  ringColor?: string
  className?: string
}

/** Floating frosted circle (160-210 px) for a single headline number. */
export function MetricBubble({
  icon,
  value,
  unit,
  label,
  detail,
  size = 176,
  loading,
  error,
  estimated,
  stale,
  ringColor,
  className,
}: MetricBubbleProps) {
  return (
    <div
      className={clsx(
        'glass-bubble flex flex-col items-center justify-center px-4 text-center',
        estimated && 'outline-dashed outline-2 outline-offset-[-6px] outline-ink-muted/50',
        className,
      )}
      style={{
        width: size,
        height: size,
        boxShadow: ringColor ? `0 0 0 4px ${ringColor}, 0 10px 40px rgba(23,33,43,0.10)` : undefined,
      }}
      aria-busy={loading || undefined}
    >
      {icon && <div className="mb-1.5 text-accent" aria-hidden>{icon}</div>}
      {loading ? (
        <>
          <Skeleton className="mb-2 h-7 w-16" />
          <Skeleton className="h-3 w-20" />
          <span className="sr-only">Loading {label}</span>
        </>
      ) : (
        <>
          {error ? (
            <p className="text-[13px] text-stale">Couldn’t load. Try again shortly.</p>
          ) : value === null ? (
            <p className="text-[13px] text-ink-muted">No reading for this hour</p>
          ) : (
            <p className="leading-none">
              <span className="text-[30px] font-medium tracking-tight">{value}</span>
              {unit && <span className="ml-1 text-[13px] text-ink-muted">{unit}</span>}
            </p>
          )}
          <p className="mt-1.5 text-[13px] text-ink-muted">{label}</p>
          {detail && <div className="mt-1 text-[12px]">{detail}</div>}
          {(estimated || stale) && (
            <p className={clsx('mt-1 text-[11px] font-medium', stale ? 'text-stale' : 'text-ink-muted')}>
              {stale ? 'Stale' : 'Estimated'}
            </p>
          )}
        </>
      )}
    </div>
  )
}
