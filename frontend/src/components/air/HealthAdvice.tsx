import { ArrowRight, HeartPulse } from 'lucide-react'
import { Link } from 'react-router'

import { aqiVar } from '../../lib/aqi'
import { useAdvice } from '../../lib/queries'
import { Skeleton } from '../ui/Skeleton'

export function HealthAdvice({ place }: { place: string }) {
  const q = useAdvice(place)
  const d = q.data
  return (
    <section aria-label="What to do today" className="flex flex-col rounded-card bg-ink p-5 text-white shadow-card">
      <header className="mb-3 flex items-center gap-2">
        <HeartPulse aria-hidden className="h-5 w-5 text-white/80" />
        <h2 className="text-[17px] font-medium">What to do today</h2>
      </header>
      {q.isLoading && <Skeleton className="h-20 w-full bg-white/20" />}
      {q.isError && <p className="text-[13px] text-white/80">Could not load health advice.</p>}
      {d && (
        <>
          {d.category ? (
            <p className="mb-2 inline-flex items-center gap-2 text-[14px] font-medium">
              <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: aqiVar(d.category_key) }} />
              Air is {d.category.toLowerCase()}
              {d.label === 'estimated' && <span className="text-[12px] font-normal text-white/70">(model estimate)</span>}
            </p>
          ) : (
            <p className="mb-2 text-[14px] text-white/80">No reading for this hour</p>
          )}
          {d.health_impact && <p className="text-[14px] leading-relaxed text-white/90">{d.health_impact}</p>}
          <p className="mt-2 text-[11px] text-white/60">{d.advice_source}</p>
        </>
      )}
      <Link
        to={{ pathname: '/finder', search: `?place=${place}` }}
        className="mt-auto inline-flex min-h-touch items-center justify-center gap-2 self-start rounded-full bg-white px-5 pt-0 text-[14px] font-medium text-ink outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
        style={{ marginTop: 16 }}
      >
        Find cleaner air <ArrowRight aria-hidden className="h-4 w-4" />
      </Link>
    </section>
  )
}
