import clsx from 'clsx'
import { Wind as WindIcon } from 'lucide-react'

import { useWind } from '../../lib/queries'
import { EstimatedBadge, StaleBadge } from '../ui/Badges'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'

const R = 70
const C = 90

function Compass({ deg, label }: { deg: number; label: string }) {
  // Meteorological direction: where the wind comes FROM. The needle's head points there.
  const ticks = Array.from({ length: 72 }, (_, i) => i * 5)
  return (
    <svg viewBox="0 0 180 180" className="h-[140px] w-[140px]" role="img" aria-label={`Wind from ${label}`}>
      {ticks.map((t) => {
        const major = t % 45 === 0
        const a = ((t - 90) * Math.PI) / 180
        const r1 = R - (major ? 9 : 5)
        return (
          <line
            key={t}
            x1={C + R * Math.cos(a)}
            y1={C + R * Math.sin(a)}
            x2={C + r1 * Math.cos(a)}
            y2={C + r1 * Math.sin(a)}
            stroke={major ? 'var(--text)' : '#b8c1c9'}
            strokeWidth={major ? 1.5 : 1}
          />
        )
      })}
      {(['N', 'E', 'S', 'W'] as const).map((d, i) => {
        const a = ((i * 90 - 90) * Math.PI) / 180
        return (
          <text key={d} x={C + (R - 20) * Math.cos(a)} y={C + (R - 20) * Math.sin(a) + 4} textAnchor="middle" fontSize={12} fontWeight={500} fill="var(--text)">
            {d}
          </text>
        )
      })}
      <g transform={`rotate(${deg} ${C} ${C})`}>
        <line x1={C} y1={C + 44} x2={C} y2={C - 44} stroke="var(--text)" strokeWidth={2} strokeLinecap="round" />
        <path d={`M ${C} ${C - 54} L ${C - 7} ${C - 40} L ${C + 7} ${C - 40} Z`} fill="var(--aqi-verypoor)" />
        <circle cx={C} cy={C + 44} r={3} fill="var(--accent)" />
      </g>
      <circle cx={C} cy={C} r={4} fill="var(--text)" />
    </svg>
  )
}

export function WindCompass({ place, className }: { place: string; className?: string }) {
  const q = useWind(place)
  const d = q.data
  return (
    <Card
      title="Wind Status"
      subtitle="Speed, gusts and direction"
      action={d && (d.stale ? <StaleBadge updatedAt={d.updated_at} stale /> : <EstimatedBadge />)}
      className={clsx('flex flex-col', className)}
    >
      {q.isLoading && <Skeleton className="h-[140px] w-full" />}
      {q.isError && <EmptyState message="Could not load wind." />}
      {d && (d.speed_kmh === null ? (
        <EmptyState />
      ) : (
        // centred, so the card can be stretched to line up with its neighbours without a gap
        <div className="flex flex-1 flex-col justify-center">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="leading-none">
                <span className="text-[40px] font-medium tracking-tight">{d.speed_kmh.toFixed(1)}</span>
                <span className="ml-1 text-[14px] text-ink-muted">km/h</span>
              </p>
              {d.gusts_kmh !== null && (
                <p className="mt-2 text-[13px] text-ink-muted">Gusts {Math.round(d.gusts_kmh)} km/h</p>
              )}
              {d.direction_compass && (
                <p className="mt-1 text-[13px] text-ink-muted">From {d.direction_compass} ({Math.round(d.direction_deg ?? 0)}°)</p>
              )}
            </div>
            {d.direction_deg !== null && <Compass deg={d.direction_deg} label={d.direction_compass ?? ''} />}
          </div>
          {d.note && (
            <p className="mt-3 flex items-start gap-2 rounded-full bg-slate-50 px-4 py-2 text-[12px]">
              <WindIcon aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
              {d.note}
            </p>
          )}
        </div>
      ))}
    </Card>
  )
}
