import { Eye, Gauge, ShieldCheck, Wind } from 'lucide-react'

import { LabelBadge, StaleBadge } from '../components/ui/Badges'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricBubble } from '../components/ui/MetricBubble'
import { aqiVar } from '../lib/aqi'
import { POLLUTANT_NAMES } from '../lib/format'
import { useAirNow } from '../lib/queries'
import { useShell } from '../lib/shell'

export function AirPage() {
  const { place } = useShell()
  const air = useAirNow(place)
  const d = air.data
  const loading = air.isLoading
  const estimated = d?.aqi_kind === 'cams'
  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">Air quality</h1>
      <section
        aria-label="Air quality now"
        className="glass-card relative flex min-h-[420px] flex-wrap items-center justify-center gap-6 overflow-hidden p-8"
      >
        <MetricBubble
          size={210}
          icon={<Gauge className="h-6 w-6" />}
          value={d?.aqi != null ? String(d.aqi) : null}
          label="AQI (India)"
          detail={d?.category && <span className="font-medium">{d.category}</span>}
          ringColor={d?.category_key ? aqiVar(d.category_key) : undefined}
          loading={loading}
          estimated={estimated}
          stale={d?.stale}
        />
        <MetricBubble
          icon={<Wind className="h-5 w-5" />}
          value={d?.main_pollutant ? POLLUTANT_NAMES[d.main_pollutant] ?? d.main_pollutant : null}
          label="Main pollutant"
          loading={loading}
          estimated={estimated}
        />
        <MetricBubble
          icon={<Eye className="h-5 w-5" />}
          value={d?.visibility_m != null ? (d.visibility_m / 1000).toFixed(1) : null}
          unit="km"
          label="Visibility"
          loading={loading}
          estimated
        />
        <MetricBubble
          icon={<ShieldCheck className="h-5 w-5" />}
          value={d?.completeness_pct != null ? d.completeness_pct.toFixed(0) : null}
          unit="%"
          label="Data completeness"
          detail={
            d?.shadow_aqi != null ? (
              <span className="text-ink-muted">
                Shadow AQI {d.shadow_aqi}
                {d.shadow_aqi_low != null && ` (${d.shadow_aqi_low}–${d.shadow_aqi_high})`}
              </span>
            ) : undefined
          }
          loading={loading}
        />
        <p className="absolute bottom-4 left-5 text-[12px] text-ink-muted">
          The pollution map arrives in Phase 5.
        </p>
      </section>
      <Card title="Data status" subtitle="Every number on VayuKavach shows its source and freshness.">
        {air.isError ? (
          <EmptyState message="Could not reach the VayuKavach API." detail={String(air.error)} />
        ) : (
          <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-muted">
            <span>Source: {d?.source ?? '…'}</span>
            {d && <LabelBadge label={d.label} />}
            {d && <StaleBadge updatedAt={d.updated_at} stale={d.stale} />}
          </div>
        )}
      </Card>
    </div>
  )
}
