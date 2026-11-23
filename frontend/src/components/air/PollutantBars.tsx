import { Leaf } from 'lucide-react'

import { AQI_LABELS, aqiKey, aqiVar } from '../../lib/aqi'
import { POLLUTANT_NAMES } from '../../lib/format'
import { useAirPollutants } from '../../lib/queries'
import { EstimatedBadge, StaleBadge } from '../ui/Badges'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'

const SEGMENTS = 30
const UNIT_TEXT: Record<string, string> = { 'ug/m3': 'µg/m³', 'mg/m3': 'mg/m³', ppm: 'ppm' }
const WINDOW: Record<string, string> = { co: '8-h', o3: '8-h' }

function SegmentBar({ subIndex }: { subIndex: number }) {
  const filled = Math.round((Math.min(subIndex, 500) / 500) * SEGMENTS)
  const colour = aqiVar(aqiKey(subIndex))
  return (
    <div className="flex h-4 gap-[2px]" aria-hidden>
      {Array.from({ length: SEGMENTS }).map((_, i) => (
        <span
          key={i}
          className="flex-1 rounded-[2px]"
          style={{ background: i < filled ? colour : '#e5e9ed' }}
        />
      ))}
    </div>
  )
}

export function PollutantBars({ place }: { place: string }) {
  const q = useAirPollutants(place)
  const d = q.data
  return (
    <Card
      title="Pollutants"
      subtitle="24-hour values (8-hour for CO and O₃) and India AQI sub-index. The highest sets the AQI."
      action={d && <StaleBadge updatedAt={d.updated_at} stale={d.stale} />}
    >
      {q.isLoading && (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      )}
      {q.isError && <EmptyState message="Could not load pollutant values." />}
      {d && (
        <ul className="space-y-3.5">
          {d.pollutants.map((p) => {
            const key = aqiKey(p.sub_index)
            return (
              <li key={p.pollutant}>
                <div className="mb-1.5 flex items-baseline justify-between gap-2 text-[14px]">
                  <span className="font-medium">
                    {POLLUTANT_NAMES[p.pollutant] ?? p.pollutant}
                    {WINDOW[p.pollutant] && (
                      <span className="ml-1 text-[11px] font-normal text-ink-muted">{WINDOW[p.pollutant]}</span>
                    )}
                  </span>
                  {p.value === null ? (
                    <span className="text-[12px] text-ink-muted">No reading</span>
                  ) : (
                    <span className="flex items-center gap-2">
                      {p.label === 'estimated' && <EstimatedBadge />}
                      <span>
                        {p.value < 10 ? p.value.toFixed(2) : Math.round(p.value)}{' '}
                        <span className="text-[12px] text-ink-muted">{UNIT_TEXT[p.unit] ?? p.unit}</span>
                      </span>
                    </span>
                  )}
                </div>
                {p.sub_index !== null && key ? (
                  <>
                    <SegmentBar subIndex={p.sub_index} />
                    <p className="mt-1 text-[11px] text-ink-muted">
                      Sub-index {p.sub_index} · {AQI_LABELS[key]}
                      {p.stations > 0 && ` · ${p.stations} station${p.stations > 1 ? 's' : ''}`}
                    </p>
                  </>
                ) : (
                  <div className="h-4 rounded-[2px] border border-dashed border-slate-300" aria-hidden />
                )}
              </li>
            )
          })}
        </ul>
      )}
      {d?.co2 && (
        <p className="mt-4 flex items-start gap-2 rounded-2xl bg-slate-50 p-3 text-[12px] text-ink-muted">
          <Leaf aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>
            CO₂ {Math.round(d.co2.value)} ppm (CAMS model, Estimated). {d.co2.note}
          </span>
        </p>
      )}
    </Card>
  )
}
