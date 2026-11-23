import { Info } from 'lucide-react'

/** Shown instead of a number when there is no data: never show a zero for missing data. */
export function EmptyState({
  message = 'No reading for this hour',
  detail,
}: {
  message?: string
  detail?: string
}) {
  return (
    <div className="flex items-start gap-2 text-[13px] text-ink-muted" role="note">
      <Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p>{message}</p>
        {detail && <p className="mt-0.5 text-[12px]">{detail}</p>}
      </div>
    </div>
  )
}
