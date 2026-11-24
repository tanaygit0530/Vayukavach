import clsx from 'clsx'
import { LocateFixed, MapPinned, Navigation, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { FinderMap } from '../components/finder/FinderMap'
import { EstimatedBadge, MeasuredBadge, StaleBadge } from '../components/ui/Badges'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Skeleton } from '../components/ui/Skeleton'
import { Tabs } from '../components/ui/Tabs'
import type { FinderMode, Goal } from '../lib/api'
import { aqiVar } from '../lib/aqi'
import { betterText, fmtMinutes, MODES, valueText } from '../lib/finder'
import { useFinder, useRoute } from '../lib/queries'
import { useShell } from '../lib/shell'

export function FinderPage() {
  const { place } = useShell()
  const [params, setParams] = useSearchParams()
  const goal: Goal = params.get('goal') === 'heat' ? 'heat' : 'air'
  const mode = (['nearby', 'daytrip', 'vacation'].includes(params.get('mode') ?? '') ? params.get('mode') : 'daytrip') as FinderMode
  const [coords, setCoords] = useState<string | null>(null)
  const [geoError, setGeoError] = useState<string | null>(null)
  const from = coords ?? place
  const finder = useFinder(goal, mode, from)
  const d = finder.data
  const [selected, setSelected] = useState<string | null>(null)
  const chosen = d?.places.find((p) => p.id === selected) ?? null
  const route = useRoute(d && chosen ? [d.origin.lat, d.origin.lon] : null, chosen ? [chosen.lat, chosen.lon] : null)

  // `chosen` is looked up in the current results, so a selection from an earlier search can't leak.

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    next.set(key, value)
    setParams(next, { replace: true })
  }

  const locate = () => {
    if (!navigator.geolocation) return setGeoError('Location is not available in this browser.')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoError(null)
        setCoords(`${pos.coords.latitude.toFixed(4)},${pos.coords.longitude.toFixed(4)}`)
      },
      () => setGeoError('Location permission was not given. Using the selected city.'),
      { timeout: 10_000 },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[15px] font-medium">
          <MapPinned aria-hidden className="h-4 w-4" /> Maps and Finder
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <Tabs
            label="What are you looking for"
            value={goal}
            onChange={(g) => set('goal', g)}
            tabs={[
              { id: 'air', label: 'Cleaner air' },
              { id: 'heat', label: 'Cooler place' },
            ]}
          />
          <button
            type="button"
            onClick={coords ? () => setCoords(null) : locate}
            className="focus-ring glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[13px] font-medium"
          >
            <LocateFixed aria-hidden className="h-4 w-4" />
            {coords ? 'Use selected city' : 'Use my location'}
          </button>
        </div>
      </div>
      {geoError && <p role="status" className="text-[12px] text-stale">{geoError}</p>}

      <div role="radiogroup" aria-label="How far" className="grid grid-cols-3 gap-3">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={mode === m.id}
            onClick={() => set('mode', m.id)}
            className={clsx(
              'focus-ring rounded-card p-4 text-left transition-colors',
              mode === m.id ? 'bg-ink text-white shadow-card' : 'glass-card hover:bg-white',
            )}
          >
            <span className="block text-[16px] font-medium">{m.title}</span>
            <span className={clsx('block text-[12px]', mode === m.id ? 'text-white/75' : 'text-ink-muted')}>{m.detail}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <Card
          title={goal === 'air' ? 'Places with cleaner air' : 'Cooler places'}
          subtitle={
            d
              ? `From ${d.origin.name}${d.origin.value !== null ? ` · here: ${valueText(goal, { value: d.origin.value })}` : ''}`
              : undefined
          }
          action={d && <StaleBadge updatedAt={d.updated_at} stale={d.stale} />}
        >
          {finder.isLoading && (
            <div className="space-y-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
          )}
          {finder.isError && <EmptyState message="The finder is unavailable right now. Try again shortly." />}
          {d && d.places.length === 0 && <EmptyState message={d.empty_reason ?? 'No places found.'} />}
          <ol className="space-y-2">
            {d?.places.map((p, i) => (
              <li key={p.id}>
                <button
                  type="button"
                  aria-pressed={selected === p.id}
                  onClick={() => setSelected(p.id)}
                  className={clsx(
                    'focus-ring flex w-full items-center gap-3 rounded-2xl border px-3 py-2.5 text-left',
                    selected === p.id ? 'border-ink bg-slate-50' : 'border-slate-100 hover:bg-slate-50',
                  )}
                >
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ink text-[12px] font-semibold text-white">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-medium">{p.name}</span>
                    <span className="block text-[12px] text-ink-muted">
                      {p.state ? `${p.state} · ` : ''}
                      {p.distance_km} km · ≈ {fmtMinutes(p.approx_minutes)}
                    </span>
                  </span>
                  <span className="text-right">
                    <span className="inline-flex items-center gap-1.5 text-[13px] font-medium">
                      {goal === 'air' && <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: aqiVar(p.category_key) }} />}
                      {valueText(goal, p)}
                    </span>
                    <span className="mt-0.5 block">{p.value_label === 'measured' ? <MeasuredBadge /> : <EstimatedBadge />}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {d && <p className="mt-3 text-[11px] text-ink-muted">{d.note}</p>}
        </Card>

        <div className="flex flex-col gap-4">
          <div className="glass-card h-[420px] overflow-hidden p-0">
            <FinderMap origin={d?.origin} places={d?.places ?? []} selected={selected} route={route.data?.geometry} onSelect={setSelected} />
          </div>
          {chosen && (
            <Card title={`Route to ${chosen.name}`} subtitle={betterText(goal, chosen.better_by) ?? undefined}>
              {route.isLoading && <Skeleton className="h-12 w-full" />}
              {route.isError && <EmptyState message="No route available right now." />}
              {route.data && (
                <dl className="grid grid-cols-3 gap-3">
                  <div><dt className="text-[12px] text-ink-muted">Distance</dt><dd className="text-[20px] font-medium">{route.data.distance_km} km</dd></div>
                  <div><dt className="text-[12px] text-ink-muted">Driving time</dt><dd className="text-[20px] font-medium">{fmtMinutes(route.data.duration_min)}</dd></div>
                  <div>
                    <dt className="text-[12px] text-ink-muted">{goal === 'air' ? 'AQI there' : 'Feels like there'}</dt>
                    <dd className="text-[20px] font-medium">{valueText(goal, chosen)}</dd>
                    <dd className="text-[11px] text-ink-muted">{chosen.value_source} · {chosen.value_label}</dd>
                  </div>
                </dl>
              )}
              {chosen.forecast.length > 0 && (
                <p className="mt-3 text-[12px] text-ink-muted">
                  Next days (estimated): {chosen.forecast.map((f) => (goal === 'air' ? Math.round(f.value) : `${f.value.toFixed(1)}°`)).join(' · ')}
                </p>
              )}
              <h3 className="mt-4 flex items-center gap-2 text-[14px] font-medium"><ShieldAlert aria-hidden className="h-4 w-4 text-accent" /> Precautions</h3>
              <ul className="mt-2 space-y-1.5 text-[13px]">
                {d?.precautions.map((p, i) => (
                  <li key={i}><span className="text-ink-muted">{p.for}: </span>{p.text}</li>
                ))}
              </ul>
              <p className="mt-1 text-[11px] text-ink-muted">{d?.precautions[0]?.source}</p>
              {route.data && (
                <a
                  href={route.data.maps_url}
                  target="_blank"
                  rel="noreferrer"
                  className="focus-ring mt-4 inline-flex min-h-touch items-center gap-2 rounded-full bg-ink px-5 text-[14px] font-medium text-white"
                >
                  <Navigation aria-hidden className="h-4 w-4" /> Start navigation
                </a>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
