import {
  BrickWall,
  Car,
  CircleDashed,
  ExternalLink,
  Factory,
  Flame,
  Fuel,
  HardHat,
  Home,
  MapPinned,
  Trash2,
  Waves,
  Wind,
  Zap,
  type LucideIcon,
} from 'lucide-react'

import { IST_TZ } from '../../lib/format'
import { useSources } from '../../lib/queries'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'

const ICONS: Record<string, LucideIcon> = {
  transport: Car,
  household_fuel: Home,
  industry: Factory,
  power_plants: Zap,
  dust: Wind,
  road_dust: Wind,
  construction_demolition: HardHat,
  waste_burning: Trash2,
  diesel_gensets: Fuel,
  brick_kilns: BrickWall,
  stubble_fires: Flame,
  sea_salt: Waves,
  outside_city: MapPinned,
  other: CircleDashed,
}

const todayIst = () => new Intl.DateTimeFormat('en-CA', { timeZone: IST_TZ }).format(new Date())
const fmtDate = (d: string) =>
  new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${d}T00:00:00Z`))

/** Share of PM2.5 by sector: IITM DSS daily values (Delhi) or a published study. */
export function SourceList({ place }: { place: string }) {
  const q = useSources(place)
  const d = q.data
  const subtitle = !d?.kind
    ? 'Share of PM2.5 by sector'
    : d.kind === 'daily'
      ? d.date === todayIst()
        ? 'Today, IITM DSS'
        : `IITM DSS, ${fmtDate(d.date!)}`
      : `Study estimate, ${d.source_year ?? 'year unknown'}`
  return (
    <Card title="Pollution Sources" subtitle={subtitle}>
      {q.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      )}
      {q.isError && <EmptyState message="Could not load source data." />}
      {d && !d.kind && (
        <EmptyState
          message="No source data for this city yet"
          detail="We only show shares from IITM's Decision Support System or a published study, never a guess."
        />
      )}
      {d?.kind && (
        <>
          <ul className="divide-y divide-slate-100">
            {d.sectors.map((s) => {
              const Icon = ICONS[s.sector] ?? CircleDashed
              return (
                <li key={s.sector} className="py-2">
                  <div className="flex items-center gap-3 text-[14px]">
                    <Icon aria-hidden className="h-4 w-4 shrink-0 text-ink-muted" strokeWidth={1.8} />
                    <span className="flex-1">{s.label}</span>
                    <span className="font-medium tabular-nums">{s.share_pct.toFixed(1)}%</span>
                  </div>
                  <div className="ml-7 mt-1.5 h-[4px] rounded-full bg-slate-100" aria-hidden>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${s.share_pct}%`, background: 'var(--text)', opacity: 0.7 }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
            {d.kind === 'daily' ? 'Modelled daily share, entered from ' : 'Modelled share from '}
            {d.source_url ? (
              <a href={d.source_url} target="_blank" rel="noreferrer" className="underline">
                {d.source_name}
                <ExternalLink aria-hidden className="ml-0.5 inline h-3 w-3 align-baseline" />
              </a>
            ) : (
              d.source_name
            )}
            . Estimated.
            {d.published_sum !== null && Math.abs(d.published_sum - 100) >= 0.05 &&
              ` Published shares add up to ${d.published_sum}%; scaled to 100.`}
          </p>
        </>
      )}
    </Card>
  )
}
