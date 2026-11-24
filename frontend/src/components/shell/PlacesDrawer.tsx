import clsx from 'clsx'
import { LoaderCircle, MapPin, Search, X } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { aqiVar } from '../../lib/aqi'
import { useDistricts, usePlaceSearch, usePlaceSummaries } from '../../lib/queries'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'

interface Props {
  open: boolean
  place: string
  onClose: () => void
  onChoose: (place: string) => void
}

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms)
    return () => window.clearTimeout(id)
  }, [value, ms])
  return debounced
}

/** Slides in from the left. Closes on X, outside click, Escape, or choosing a place. */
export function PlacesDrawer({ open, place, onClose, onChoose }: Props) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const term = useDebounced(query)
  const districts = useDistricts()
  const ids = districts.data?.map((d) => d.id) ?? []
  const summaries = usePlaceSummaries(open ? ids : [])
  const search = usePlaceSearch(open ? term : '')

  const dismiss = useCallback(() => {
    setQuery('')
    onClose()
  }, [onClose])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss()
      if (event.key === 'Tab' && panelRef.current) {
        // keep focus inside the drawer while it is open
        const items = panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input, [href]',
        )
        if (!items.length) return
        const first = items[0]
        const last = items[items.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, dismiss])

  const choose = (id: string) => {
    onChoose(id)
    dismiss()
  }

  const byId = new Map((summaries.data?.places ?? []).map((p) => [p.id, p]))
  const searching = term.trim().length >= 2

  return (
    <div
      className={clsx('fixed inset-0 z-[1000]', open ? 'pointer-events-auto' : 'pointer-events-none')}
      aria-hidden={!open}
      // closed: keep the slide-out animation but take its buttons out of the tab order
      inert={!open}
    >
      <div
        data-testid="drawer-backdrop"
        onClick={dismiss}
        className={clsx(
          'absolute inset-0 bg-ink/20 transition-opacity duration-200',
          open ? 'opacity-100' : 'opacity-0',
        )}
      />
      <div
        ref={panelRef}
        id="places-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={clsx(
          'glass-card absolute inset-y-3 left-3 flex w-[min(380px,calc(100vw-24px))] flex-col p-5 transition-transform duration-200 ease-out',
          open ? 'translate-x-0' : '-translate-x-[110%]',
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id={titleId} className="text-[18px] font-medium">
            Places
          </h2>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Close places"
            className="focus-ring grid h-[44px] w-[44px] place-items-center rounded-full text-ink-muted hover:bg-slate-100"
          >
            <X aria-hidden className="h-5 w-5" />
          </button>
        </div>

        <label className="relative mb-4 block">
          <span className="sr-only">Search a city in India</span>
          <Search aria-hidden className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a city in India"
            className="focus-ring min-h-touch w-full rounded-full border border-slate-200 bg-white pl-10 pr-4 text-[14px] placeholder:text-ink-muted"
          />
        </label>

        <div className="-mx-1 flex-1 overflow-y-auto px-1">
          {searching ? (
            <section aria-label="Search results">
              {search.isFetching && (
                <p className="flex items-center gap-2 text-[13px] text-ink-muted">
                  <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" /> Searching…
                </p>
              )}
              {search.isError && <EmptyState message="Place search is unavailable right now." />}
              {search.data && search.data.results.length === 0 && (
                <EmptyState message="No matching place in India." />
              )}
              <ul className="space-y-1">
                {search.data?.results.map((r) => (
                  <li key={`${r.name}-${r.lat}-${r.lon}`}>
                    <button
                      type="button"
                      disabled={!r.covered_district}
                      onClick={() => r.covered_district && choose(r.covered_district)}
                      className="focus-ring flex min-h-touch w-full items-center gap-3 rounded-2xl px-3 py-2 text-left hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent"
                    >
                      <MapPin aria-hidden className="h-4 w-4 shrink-0 text-ink-muted" />
                      <span className="flex-1">
                        <span className="block text-[14px] font-medium">{r.name}</span>
                        <span className="block text-[12px] text-ink-muted">
                          {[r.district, r.state].filter(Boolean).join(', ')}
                          {!r.covered_district && ' · Not covered yet'}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <section aria-label="Covered cities">
              <h3 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-muted">
                Covered cities
              </h3>
              {districts.isLoading && (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-[52px] w-full" />
                  ))}
                </div>
              )}
              {districts.isError && <EmptyState message="Could not load places. Is the API running?" />}
              <ul className="space-y-1">
                {districts.data?.map((d) => {
                  const s = byId.get(d.id)
                  const active = d.id === place
                  return (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => choose(d.id)}
                        aria-current={active ? 'true' : undefined}
                        className={clsx(
                          'focus-ring flex min-h-touch w-full items-center gap-3 rounded-2xl px-3 py-2 text-left',
                          active ? 'bg-ink text-white' : 'hover:bg-slate-100',
                        )}
                      >
                        <span
                          aria-hidden
                          className={clsx(
                            'h-3 w-3 shrink-0 rounded-full',
                            s?.aqi_label === 'estimated' &&
                              'outline-dashed outline-1 outline-offset-2 outline-ink-muted',
                          )}
                          style={{ background: aqiVar(s?.category_key) }}
                        />
                        <span className="flex-1">
                          <span className="block text-[14px] font-medium">{d.name}</span>
                          <span className={clsx('block text-[12px]', active ? 'text-white/75' : 'text-ink-muted')}>
                            {d.state}
                          </span>
                        </span>
                        <span className="text-right text-[12px]">
                          {summaries.isLoading ? (
                            <Skeleton className="h-4 w-16" />
                          ) : (
                            <>
                              <span className="block font-medium">
                                {s?.aqi != null ? `AQI ${s.aqi}` : 'No AQI'}
                                {s?.aqi_label === 'estimated' && ' (est.)'}
                              </span>
                              <span className={active ? 'text-white/75' : 'text-ink-muted'}>
                                {s?.temperature != null ? `${Math.round(s.temperature)}°C` : '–'}
                              </span>
                            </>
                          )}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </section>
          )}
        </div>
        <p className="mt-3 text-[11px] text-ink-muted">
          AQI: CPCB (Measured) or CAMS model (est.). Temperature: Open-Meteo.
        </p>
      </div>
    </div>
  )
}
