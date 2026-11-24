import clsx from 'clsx'
import { useQuery } from '@tanstack/react-query'
import { Download, FileText } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import { LabelBadge, StaleBadge } from '../components/ui/Badges'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LoadingText } from '../components/ui/Skeleton'
import { ApiError, apiGet, apiUrl, type GapReport } from '../lib/api'
import { useDistricts } from '../lib/queries'
import { istDate } from '../lib/time'
import { useShell } from '../lib/shell'

const POLLUTANT: Record<string, string> = { pm25: 'PM2.5', pm10: 'PM10', no2: 'NO₂', so2: 'SO₂', co: 'CO', o3: 'O₃', nh3: 'NH₃' }

function hhmm(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(new Date(iso))
}

function pctTone(p: number): string {
  if (p >= 90) return 'bg-aqi-good'
  if (p >= 75) return 'bg-aqi-moderate'
  return 'bg-aqi-poor'
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="glass-card p-4">
      <p className="text-[12px] text-ink-muted">{label}</p>
      <p className="mt-1 text-[28px] font-light leading-none">{value}</p>
      {note && <p className="mt-2 text-[12px] text-ink-muted">{note}</p>}
    </div>
  )
}

export function ReportsPage() {
  const { place } = useShell()
  const [params, setParams] = useSearchParams()
  const districts = useDistricts()
  const city = districts.data?.find((d) => d.id === place)?.name ?? place
  const today = istDate()
  const day = params.get('date') ?? istDate(-1)
  const [showAll, setShowAll] = useState(false)

  const report = useQuery({
    queryKey: ['gaps', place, day],
    queryFn: () => apiGet<GapReport>(`/reports/${place}/gaps`, { date: day }),
    retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 2,
  })
  const r = report.data

  const below = useMemo(() => r?.stations.filter((s) => s.pct < 75) ?? [], [r])
  const rows = showAll ? (r?.stations ?? []) : below.slice(0, 30)
  const stationCount = useMemo(() => new Set(r?.stations.map((s) => s.station_id)).size, [r])

  const setDay = (v: string) => {
    const next = new URLSearchParams(params)
    next.set('date', v)
    setParams(next, { replace: true })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[15px] font-medium">
          <FileText aria-hidden className="h-4 w-4" /> Data report · {city}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <label className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[13px]">
            <span className="text-ink-muted">Date</span>
            <input
              type="date"
              value={day}
              max={today}
              onChange={(e) => e.target.value && setDay(e.target.value)}
              className="focus-ring rounded-md bg-transparent font-medium"
            />
          </label>
          <a
            href={apiUrl(`/reports/${place}/gaps`, { date: day, format: 'csv' })}
            download
            className="focus-ring inline-flex min-h-touch items-center gap-2 rounded-full bg-ink px-4 text-[13px] text-white"
          >
            <Download aria-hidden className="h-4 w-4" /> Download CSV
          </a>
        </div>
      </div>

      {report.isLoading && <LoadingText label="Loading the report" />}
      {report.isError && (
        <Card>
          <EmptyState
            message="This report is unavailable."
            detail={report.error instanceof ApiError && report.error.status === 404 ? 'This place is not covered yet.' : 'Please try again shortly.'}
          />
        </Card>
      )}

      {r && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-muted">
            <span>Source: {r.source}</span>
            <LabelBadge label={r.label} />
            <StaleBadge updatedAt={r.updated_at} stale={r.stale} />
            {day === today && <span>Today is still in progress: numbers will change.</span>}
          </div>

          {r.stations.length === 0 ? (
            <Card>
              <EmptyState message={`No station data for ${city} on ${day}.`} detail="Either no CPCB station is in this district, or collection had not started on this date." />
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Stat
                  label="Data completeness"
                  value={r.completeness_pct != null ? `${r.completeness_pct.toFixed(0)}%` : '—'}
                  note={`Expected hourly readings that arrived, ${stationCount} stations`}
                />
                <Stat label="Stations silent ≥ 3 h" value={String(r.silent_stations.length)} note="Stopped reporting for 3 hours or more" />
                <Stat label="City-wide silent hours" value={String(r.city_silent_hours.length)} note="Hours when a quarter or more of stations were silent" />
                <Stat label="PM readings near 999" value={String(r.readings_near_limit.length)} note="950 µg/m³ or more; 999+ is left out of the AQI, as CPCB does" />
              </div>

              <Card title="Were gaps worse in polluted hours?" subtitle="Compares missing readings in the most polluted hours with the cleanest hours of the day.">
                {r.gap_bias ? (
                  <div className="flex flex-wrap items-center gap-6 text-[14px]">
                    <p>
                      Polluted hours missing: <span className="font-medium">{r.gap_bias.polluted_hours_missing_pct ?? '—'}%</span>
                    </p>
                    <p>
                      Clean hours missing: <span className="font-medium">{r.gap_bias.clean_hours_missing_pct ?? '—'}%</span>
                    </p>
                    <p
                      className={clsx(
                        'rounded-full px-3 py-1 text-[13px]',
                        r.gap_bias.flagged ? 'bg-amber-50 text-stale ring-1 ring-amber-200' : 'bg-slate-100',
                      )}
                    >
                      {r.gap_bias.flagged ? 'Flagged: gaps clustered in polluted hours' : 'Not flagged'}
                    </p>
                  </div>
                ) : (
                  <EmptyState message="Not enough readings to compare." />
                )}
              </Card>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card title="Silent stations" subtitle="Times in IST">
                  {r.silent_stations.length === 0 ? (
                    <EmptyState message="No station went silent for 3 hours or more." />
                  ) : (
                    <ul className="divide-y divide-slate-100 text-[13px]">
                      {r.silent_stations.map((s, i) => (
                        <li key={`${s.station_id}-${i}`} className="flex justify-between gap-3 py-2">
                          <span>{s.name}</span>
                          <span className="shrink-0 tabular-nums text-ink-muted">
                            {hhmm(s.from)}–{hhmm(s.to)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
                <Card title="Flagged hours" subtitle="City-wide silence and PM readings near the 999 cut-off (IST)">
                  {r.city_silent_hours.length === 0 && r.readings_near_limit.length === 0 ? (
                    <EmptyState message="No flagged hours on this day." />
                  ) : (
                    <ul className="divide-y divide-slate-100 text-[13px]">
                      {r.city_silent_hours.map((h) => (
                        <li key={h} className="flex justify-between py-2">
                          <span>A quarter or more of stations silent</span>
                          <span className="tabular-nums text-ink-muted">{hhmm(h)}</span>
                        </li>
                      ))}
                      {[...r.readings_near_limit].sort((a, b) => a.hour.localeCompare(b.hour)).map((x, i) => (
                        <li key={`n${i}`} className="flex justify-between gap-3 py-2">
                          <span>
                            {x.name ?? `Station ${x.station_id}`}: {POLLUTANT[x.pollutant] ?? x.pollutant} {x.value ?? '—'}
                            {x.at_or_over_999 && ' (left out of AQI)'}
                          </span>
                          <span className="shrink-0 tabular-nums text-ink-muted">{hhmm(x.hour)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>

              <Card
                title="Station completeness"
                subtitle={showAll ? `All ${r.stations.length} station-pollutant rows, lowest first` : `${below.length} rows below 75%, lowest first`}
                action={
                  <button type="button" onClick={() => setShowAll((s) => !s)} className="focus-ring min-h-touch rounded-full bg-slate-100 px-4 text-[13px] hover:bg-slate-200">
                    {showAll ? 'Only below 75%' : 'Show all'}
                  </button>
                }
              >
                {rows.length === 0 ? (
                  <EmptyState message="Every station reported at least 75% of its hours." />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-[13px]">
                      <thead className="text-[12px] text-ink-muted">
                        <tr>
                          <th className="py-2 font-normal">Station</th>
                          <th className="py-2 font-normal">Pollutant</th>
                          <th className="py-2 font-normal">Hours received</th>
                          <th className="w-[30%] py-2 font-normal">Completeness</th>
                          <th className="py-2 text-right font-normal">Longest gap</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {rows.map((s) => (
                          <tr key={`${s.station_id}-${s.pollutant}`}>
                            <td className="py-2 pr-3">{s.name}</td>
                            <td className="py-2">{POLLUTANT[s.pollutant] ?? s.pollutant}</td>
                            <td className="py-2 tabular-nums">
                              {s.received} / {s.expected}
                            </td>
                            <td className="py-2">
                              <div className="flex items-center gap-2">
                                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                                  <div className={clsx('h-full rounded-full', pctTone(s.pct))} style={{ width: `${s.pct}%` }} />
                                </div>
                                <span className="w-12 text-right tabular-nums">{s.pct.toFixed(0)}%</span>
                              </div>
                            </td>
                            <td className="py-2 text-right tabular-nums">{s.longest_gap_hours} h</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
              <p className="text-[12px] text-ink-muted">{r.wording}</p>
            </>
          )}
        </>
      )}
    </div>
  )
}
