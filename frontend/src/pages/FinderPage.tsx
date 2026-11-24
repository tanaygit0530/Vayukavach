import clsx from 'clsx'
import { LocateFixed, MapPinned, Navigation, ShieldAlert, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { FinderMap } from '../components/finder/FinderMap'
import { EstimatedBadge, MeasuredBadge, StaleBadge } from '../components/ui/Badges'
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

  const wide = useWide()
  // keep the pins clear of the floating panels when fitting the map
  const padTopLeft: [number, number] = wide ? [440, 110] : [40, 40]
  const padBottomRight: [number, number] = wide ? [chosen ? 420 : 40, 40] : [40, 40]

  const list = (
    <>
      <header className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-medium leading-tight">{goal === 'air' ? 'Places with cleaner air' : 'Cooler places'}</h2>
          {d && (
            <p className="mt-1 text-[13px] text-ink-muted">
              From {d.origin.name}
              {d.origin.value !== null ? ` · here: ${valueText(goal, { value: d.origin.value })}` : ''}
            </p>
          )}
        </div>
        {d && <StaleBadge updatedAt={d.updated_at} stale={d.stale} />}
      </header>
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
                selected === p.id ? 'border-ink bg-white' : 'border-slate-100 bg-white/60 hover:bg-white',
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
    </>
  )

  const routeCard = chosen && (
    <>
      <header className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-medium leading-tight">Route to {chosen.name}</h2>
          {betterText(goal, chosen.better_by) && <p className="mt-1 text-[13px] text-ink-muted">{betterText(goal, chosen.better_by)}</p>}
        </div>
        <button type="button" onClick={() => setSelected(null)} aria-label="Close route" className="focus-ring grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 hover:bg-slate-200">
          <X aria-hidden className="h-4 w-4" />
        </button>
      </header>
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
    </>
  )

  return (
    // Desktop: the map fills the page and the controls, list and route float over it.
    // Phones: the same pieces stacked.
    <div className="relative flex flex-col gap-3 lg:isolate lg:h-[calc(100vh-136px)] lg:min-h-[640px] lg:overflow-hidden lg:rounded-card lg:shadow-card">
      <div className="h-[380px] overflow-hidden rounded-card lg:absolute lg:inset-0 lg:h-auto lg:rounded-none">
        <FinderMap
          origin={d?.origin}
          places={d?.places ?? []}
          selected={selected}
          route={route.data?.geometry}
          onSelect={setSelected}
          padTopLeft={padTopLeft}
          padBottomRight={padBottomRight}
        />
      </div>

      <div className="order-first flex flex-wrap items-center gap-2 lg:absolute lg:inset-x-4 lg:top-4 lg:z-[500]">
        <h1 className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[15px] font-medium">
          <MapPinned aria-hidden className="h-4 w-4" /> Maps and Finder
        </h1>
        <Tabs
          label="What are you looking for"
          value={goal}
          onChange={(g) => set('goal', g)}
          tabs={[
            { id: 'air', label: 'Cleaner air' },
            { id: 'heat', label: 'Cooler place' },
          ]}
        />
        <div role="radiogroup" aria-label="How far" className="glass-card inline-flex rounded-full p-1">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={mode === m.id}
              onClick={() => set('mode', m.id)}
              className={clsx(
                'focus-ring min-h-[40px] rounded-full px-3 text-left leading-tight transition-colors',
                mode === m.id ? 'bg-ink text-white' : 'hover:bg-white',
              )}
            >
              <span className="block text-[13px] font-medium">{m.title}</span>
              <span className={clsx('block text-[10px]', mode === m.id ? 'text-white/75' : 'text-ink-muted')}>{m.detail}</span>
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={coords ? () => setCoords(null) : locate}
          className="focus-ring glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[13px] font-medium lg:ml-auto"
        >
          <LocateFixed aria-hidden className="h-4 w-4" />
          {coords ? 'Use selected city' : 'Use my location'}
        </button>
        {geoError && <p role="status" className="w-full text-[12px] text-stale">{geoError}</p>}
      </div>

      <section
        aria-label={goal === 'air' ? 'Places with cleaner air' : 'Cooler places'}
        className="glass-card p-4 lg:absolute lg:bottom-4 lg:left-4 lg:top-[84px] lg:z-[500] lg:w-[400px] lg:overflow-y-auto"
      >
        {list}
      </section>

      {routeCard && (
        <section
          aria-label={`Route to ${chosen?.name}`}
          className="glass-card p-5 lg:absolute lg:bottom-4 lg:right-4 lg:z-[500] lg:max-h-[calc(100%-100px)] lg:w-[380px] lg:overflow-y-auto"
        >
          {routeCard}
        </section>
      )}
    </div>
  )
}

function useWide(): boolean {
  const query = '(min-width: 1024px)'
  const [wide, setWide] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(query)
    if (!mq) return
    const on = () => setWide(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return wide
}
