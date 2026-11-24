import { Eye, Gauge, ShieldCheck, Wind } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link } from 'react-router'

import { AqiChart } from '../components/air/AqiChart'
import { HealthAdvice } from '../components/air/HealthAdvice'
import { PollutantBars } from '../components/air/PollutantBars'
import { SourceList } from '../components/air/SourceList'
import { WindCompass } from '../components/air/WindCompass'
import { MetricBubble } from '../components/ui/MetricBubble'
import { aqiVar } from '../lib/aqi'
import { POLLUTANT_NAMES } from '../lib/format'
import { useAirNow, useDistricts } from '../lib/queries'
import { useShell } from '../lib/shell'

// Leaflet is the largest dependency: load it after the numbers are on screen.
const PollutionMap = lazy(() => import('../components/air/PollutionMap').then((m) => ({ default: m.PollutionMap })))

const KIND_TEXT = { official: 'CPCB', measured: 'Stations', cams: 'Model' } as const

function Bubbles({ place, size }: { place: string; size: 'desktop' | 'phone' }) {
  const air = useAirNow(place)
  const d = air.data
  const loading = air.isLoading
  const estimated = d?.aqi_kind === 'cams'
  const s = size === 'desktop' ? [210, 170, 170, 184] : [156, 156, 156, 156]
  const items: { key: string; node: ReactNode; pos: string }[] = [
    {
      key: 'aqi',
      pos: 'left-[6%] top-[10%]',
      node: (
        <MetricBubble
          size={s[0]}
          icon={<Gauge className="h-6 w-6" />}
          value={d?.aqi != null ? String(d.aqi) : null}
          label={`AQI · ${d?.aqi_kind ? KIND_TEXT[d.aqi_kind] : 'India'}`}
          detail={d?.category && <span className="font-medium">{d.category}</span>}
          ringColor={d?.category_key ? aqiVar(d.category_key) : undefined}
          loading={loading}
          error={air.isError}
          estimated={estimated}
          stale={d?.stale}
        />
      ),
    },
    {
      key: 'main',
      pos: 'left-[30%] top-[46%]',
      node: (
        <MetricBubble
          size={s[1]}
          icon={<Wind className="h-5 w-5" />}
          value={d?.main_pollutant ? (POLLUTANT_NAMES[d.main_pollutant] ?? d.main_pollutant) : null}
          label="Main pollutant"
          loading={loading}
          error={air.isError}
          estimated={estimated}
        />
      ),
    },
    {
      key: 'vis',
      pos: 'right-[30%] top-[8%]',
      node: (
        <MetricBubble
          size={s[2]}
          icon={<Eye className="h-5 w-5" />}
          value={d?.visibility_m != null ? (d.visibility_m / 1000).toFixed(1) : null}
          unit="km"
          label="Visibility"
          loading={loading}
          error={air.isError}
          estimated
        />
      ),
    },
    {
      key: 'complete',
      pos: 'right-[9%] top-[40%]',
      node: (
        <MetricBubble
          size={s[3]}
          icon={<ShieldCheck className="h-5 w-5" />}
          value={d?.completeness_pct != null ? d.completeness_pct.toFixed(0) : null}
          unit="%"
          label="Data completeness"
          detail={
            <>
              {d?.shadow_aqi != null && (
                <span className="block text-ink-muted">
                  Shadow AQI {d.shadow_aqi}
                  {d.shadow_aqi_low != null && ` (${d.shadow_aqi_low}–${d.shadow_aqi_high})`}
                </span>
              )}
              <Link
                to={{ pathname: '/reports', search: `?place=${place}` }}
                className="focus-ring mt-0.5 inline-block rounded font-medium text-ink underline underline-offset-2"
              >
                Data report
              </Link>
            </>
          }
          loading={loading}
          error={air.isError}
        />
      ),
    },
  ]
  if (size === 'phone') {
    return (
      <div className="grid grid-cols-2 justify-items-center gap-3 md:hidden">
        {items.map((i) => (
          <div key={i.key}>{i.node}</div>
        ))}
      </div>
    )
  }
  return (
    <div className="pointer-events-none absolute inset-0 z-[450] hidden md:block">
      {items.map((i) => (
        <div key={i.key} className={`pointer-events-auto absolute ${i.pos}`}>
          {i.node}
        </div>
      ))}
    </div>
  )
}

export function AirPage() {
  const { place } = useShell()
  const districts = useDistricts()
  const district = districts.data?.find((d) => d.id === place)
  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">Air quality in {district?.name ?? place}</h1>
      <section aria-label="Pollution map and current air quality" className="relative isolate">
        <Suspense fallback={<div className="h-[360px] rounded-card bg-slate-200/60 shadow-card md:h-[540px]" aria-label="Loading map" role="status" />}>
          <PollutionMap place={place} district={district} className="h-[360px] shadow-card md:h-[540px]" />
        </Suspense>
        <Bubbles place={place} size="desktop" />
      </section>
      <Bubbles place={place} size="phone" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <AqiChart place={place} />
        <HealthAdvice place={place} />
        <SourceList place={place} />
        <PollutantBars place={place} />
        <WindCompass place={place} />
      </div>
    </div>
  )
}
