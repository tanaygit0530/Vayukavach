import { ArrowRight, Droplets, Gauge, Moon, Sun, Sunrise, Sunset, Thermometer, Waves } from 'lucide-react'
import { Link } from 'react-router'

import type { WeatherDay, WeatherHour, WeatherNowFull } from '../../lib/api'
import { aqiVar } from '../../lib/aqi'
import { formatIstTime } from '../../lib/format'
import { useAirNow, useHeatSummary, useSun, useUv } from '../../lib/queries'
import {
  cloudNote,
  fmtClock,
  fmtDuration,
  fmtHourShort,
  rainNote,
  sunFraction,
  swingNote,
  trendPoints,
  uvAngle,
} from '../../lib/weather'
import { EstimatedBadge, MeasuredBadge, StaleBadge } from '../ui/Badges'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { SkyIcon } from '../ui/SkyIcon'
import { Skeleton } from '../ui/Skeleton'
import { Skyline } from './Skyline'

const deg = (v: number | null | undefined) => (v === null || v === undefined ? null : `${Math.round(v)}°`)

// ---------------------------------------------------------------- My location

export function MyLocationCard({ place, name, state, now, loading }: {
  place: string; name: string; state: string; now: WeatherNowFull | undefined; loading: boolean
}) {
  const sun = useSun(place).data?.days[0]
  const night = !!sun && sunFraction(sun.sunrise, sun.sunset, new Date()) === null
  return (
    <Card className="relative flex min-h-[300px] flex-1 flex-col overflow-hidden" as="article">
      <div className="relative z-10 flex items-start justify-between">
        <div>
          <h2 className="text-[17px] font-medium">{name}</h2>
          <p className="text-[13px] text-ink-muted">{state}</p>
        </div>
        {now && (now.stale ? <StaleBadge updatedAt={now.updated_at} stale /> : <EstimatedBadge />)}
      </div>
      {loading ? (
        <Skeleton className="relative z-10 mt-6 h-16 w-40" />
      ) : now?.temperature == null ? (
        <div className="relative z-10 mt-6"><EmptyState /></div>
      ) : (
        <div className="relative z-10 mt-5 flex items-center justify-between gap-3">
          <div className="flex flex-col items-center gap-1">
            <SkyIcon code={now.weather_code} className="h-12 w-12" night={night} />
            <p className="text-[14px] font-medium">{now.condition ?? 'Unknown'}</p>
          </div>
          <div className="text-right">
            <p className="text-[52px] font-medium leading-none tracking-tight">
              {Math.round(now.temperature)}
              <span className="text-[30px] align-top">°C</span>
            </p>
            <p className="mt-2 text-[14px] text-ink-muted">
              H:{deg(now.today_high) ?? '–'} &nbsp;L:{deg(now.today_low) ?? '–'}
            </p>
          </div>
        </div>
      )}
      <Skyline className="pointer-events-none absolute inset-x-0 bottom-0 h-[45%] min-h-[110px] w-full" />
    </Card>
  )
}

// ---------------------------------------------------------------- Feels like

export function FeelsLikeCard({ place, now, loading }: { place: string; now: WeatherNowFull | undefined; loading: boolean }) {
  const heat = useHeatSummary(place)
  return (
    <Card title="Feels like" subtitle="Apparent temperature: air, humidity, wind and sun together">
      {loading ? (
        <Skeleton className="h-14 w-32" />
      ) : now?.apparent_temperature == null ? (
        <EmptyState />
      ) : (
        <>
          <p className="flex items-center gap-2 leading-none">
            <Thermometer aria-hidden className="h-6 w-6 text-accent" />
            <span className="text-[40px] font-medium tracking-tight">{Math.round(now.apparent_temperature)}°C</span>
          </p>
          {now.feels_like_reason && <p className="mt-3 text-[14px]">{now.feels_like_reason}</p>}
        </>
      )}
      <Link
        to={{ pathname: '/heat', search: `?place=${place}` }}
        className="focus-ring mt-4 inline-flex min-h-touch items-center gap-2 rounded-full bg-slate-100 px-4 text-[13px] font-medium hover:bg-slate-200"
      >
        Heat risk: {heat.data?.level_name ?? (heat.isLoading ? '…' : 'not available')}
        <span className="text-ink-muted">→ Heat alerts</span>
        <ArrowRight aria-hidden className="h-4 w-4" />
      </Link>
    </Card>
  )
}

// ---------------------------------------------------------------- Temperature trend

export function TempTrend({ hours, loading, now = new Date() }: { hours: WeatherHour[] | undefined; loading: boolean; now?: Date }) {
  const points = hours ? trendPoints(hours, now) : []
  const temps = points.map((p) => p.temp).filter((t): t is number => t !== null)
  const lo = Math.min(...temps)
  const hi = Math.max(...temps)
  const span = Math.max(1, hi - lo)
  const top = (t: number) => 8 + (1 - (t - lo) / span) * 70 // px from top, inside a 130 px track
  return (
    <Card
      title="Temperature trend"
      subtitle="Today, 7 AM–7 PM. Earlier hours are model analysis, later hours are forecast."
      className="lg:col-span-2"
    >
      {loading && <Skeleton className="h-[160px] w-full" />}
      {!loading && temps.length === 0 && <EmptyState message="No hourly temperatures for today yet." />}
      {!loading && temps.length > 0 && (
        <ol className="grid grid-cols-[repeat(13,minmax(34px,1fr))] gap-1 overflow-x-auto pb-1" aria-label="Hourly temperature">
          {points.map((p) => (
            <li key={p.hour} className="flex flex-col items-center">
              <div className="relative h-[130px] w-full">
                {p.temp !== null && (
                  <>
                    {p.isNow && (
                      <span
                        aria-hidden
                        className="absolute left-1/2 w-[30px] -translate-x-1/2 rounded-b-full"
                        style={{ top: top(p.temp) + 18, bottom: 0, background: 'linear-gradient(180deg, rgba(31,157,85,.35), rgba(31,157,85,0))' }}
                      />
                    )}
                    <span
                      className={
                        'absolute left-1/2 grid h-[38px] w-[38px] -translate-x-1/2 place-items-center rounded-full text-[12px] font-medium ' +
                        (p.isNow
                          ? 'bg-accent text-white shadow-bubble'
                          : p.isForecast
                            ? 'glass-bubble text-ink-muted outline-dashed outline-1 outline-slate-300'
                            : 'glass-bubble text-ink')
                      }
                      style={{ top: top(p.temp) }}
                      title={`${fmtHourShort(p.hour)}: ${Math.round(p.temp)}°C${p.isForecast ? ' (forecast)' : ''}`}
                    >
                      {p.isNow ? 'Now' : deg(p.temp)}
                      <span className="sr-only">
                        {fmtHourShort(p.hour)} {Math.round(p.temp)} degrees{p.isForecast ? ', forecast' : ''}
                      </span>
                    </span>
                  </>
                )}
              </div>
              <span className={'mt-1 whitespace-nowrap text-[11px] ' + (p.isNow ? 'font-semibold text-ink' : 'text-ink-muted')}>
                {fmtHourShort(p.hour)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------- 10-day forecast

export function ForecastList({ days, loading }: { days: WeatherDay[] | undefined; loading: boolean }) {
  const list = (days ?? []).slice(1, 11) // tomorrow + 9: today's high/low are on the location card
  const lows = list.map((d) => d.temperature_min).filter((v): v is number => v !== null)
  const highs = list.map((d) => d.temperature_max).filter((v): v is number => v !== null)
  const lo = Math.min(...lows)
  const hi = Math.max(...highs)
  const span = Math.max(1, hi - lo)
  const weekday = (date: string) =>
    new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`))
  return (
    <Card title="10-day forecast" subtitle="Daily low and high on one shared scale" className="flex flex-col">
      {loading && <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}</div>}
      {!loading && list.length === 0 && <EmptyState message="No forecast stored yet." />}
      <ul className="flex flex-1 flex-col justify-between divide-y divide-slate-100">
        {list.map((d) => {
          const ok = d.temperature_min !== null && d.temperature_max !== null
          return (
            <li key={d.date} className="grid grid-cols-[64px_24px_40px_1fr_40px] items-center gap-2 py-2.5 text-[14px]">
              <span className="text-ink-muted">{weekday(d.date)}</span>
              <span title={d.condition ?? undefined}>
                <SkyIcon code={d.weather_code} className="h-5 w-5" />
                <span className="sr-only">{d.condition}</span>
              </span>
              <span className="text-right">{deg(d.temperature_min) ?? '–'}</span>
              <span className="relative h-[6px] rounded-full bg-slate-100" aria-hidden>
                {ok && (
                  <span
                    className="absolute inset-y-0 rounded-full"
                    style={{
                      left: `${((d.temperature_min! - lo) / span) * 100}%`,
                      right: `${100 - ((d.temperature_max! - lo) / span) * 100}%`,
                      background: 'linear-gradient(90deg, #3bb44a, #f5d547 60%, #f08a3c)',
                    }}
                  />
                )}
              </span>
              <span className="font-medium">{deg(d.temperature_max) ?? '–'}</span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

// ---------------------------------------------------------------- Sun arc

export function SunArc({ place, now = new Date() }: { place: string; now?: Date }) {
  const q = useSun(place)
  const today = q.data?.days[0]
  const f = today ? sunFraction(today.sunrise, today.sunset, now) : null
  const R = 92
  const cx = 110
  const cy = 112
  const pt = (t: number) => [cx - R * Math.cos(Math.PI * t), cy - R * Math.sin(Math.PI * t)] as const
  const [sx, sy] = pt(f ?? 0)
  const arcTo = (t: number) => {
    const [x, y] = pt(t)
    return `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x} ${y}`
  }
  const isNight = today && f === null
  return (
    <Card title="Sunrise & sunset" subtitle="Daylight today">
      {q.isLoading && <Skeleton className="h-[150px] w-full" />}
      {q.isError && <EmptyState message="Could not load sun times." />}
      {today && (
        <>
          <svg viewBox="0 0 220 128" className="mx-auto h-auto w-full max-w-[260px]" role="img"
               aria-label={isNight ? 'The sun has set' : `Sun is ${Math.round((f ?? 0) * 100)}% of the way through the day`}>
            <path d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`} fill="none" stroke="#d5dbe1" strokeWidth={2} strokeDasharray="3 5" />
            {f !== null && <path d={arcTo(f)} fill="none" stroke="#f5b700" strokeWidth={3} strokeLinecap="round" />}
            <line x1={cx - R - 8} x2={cx + R + 8} y1={cy} y2={cy} stroke="#e3e8ec" />
            {f !== null ? (
              <g>
                <circle cx={sx} cy={sy} r={10} fill="#fff" stroke="#f5b700" strokeWidth={3} />
                <circle cx={sx} cy={sy} r={4} fill="#f5b700" />
              </g>
            ) : (
              <circle cx={cx + R} cy={cy} r={6} fill="#b8c1c9" />
            )}
            <text x={cx} y={cy - 34} textAnchor="middle" fontSize={11} fill="var(--text-muted)">Daylight</text>
            <text x={cx} y={cy - 16} textAnchor="middle" fontSize={16} fontWeight={500} fill="var(--accent)">
              {fmtDuration(today.daylight_seconds) ?? '–'}
            </text>
          </svg>
          <div className="mt-1 flex justify-between text-[13px]">
            <div>
              <p className="flex items-center gap-1 text-ink-muted"><Sunrise aria-hidden className="h-4 w-4 text-amber-500" /> Sunrise</p>
              <p className="font-medium">{fmtClock(today.sunrise) ?? '–'}</p>
            </div>
            {isNight && <p className="flex items-center gap-1 self-end text-[12px] text-ink-muted"><Moon aria-hidden className="h-4 w-4" /> After sunset</p>}
            <div className="text-right">
              <p className="flex items-center justify-end gap-1 text-ink-muted"><Sunset aria-hidden className="h-4 w-4 text-orange-500" /> Sunset</p>
              <p className="font-medium">{fmtClock(today.sunset) ?? '–'}</p>
            </div>
          </div>
        </>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------- UV gauge

const UV_BANDS: [number, number, string][] = [
  [0, 3, '#3bb44a'], [3, 6, '#f5d547'], [6, 8, '#f08a3c'], [8, 11, '#e5483f'], [11, 12, '#8e44ad'],
] // prettier-ignore

export function UvGauge({ place }: { place: string }) {
  const q = useUv(place)
  const d = q.data
  const R = 80
  const cx = 100
  const cy = 100
  const arc = (a: number, b: number) => {
    const p = (v: number) => {
      const t = Math.PI * (1 - v / 12)
      return [cx + R * Math.cos(t), cy - R * Math.sin(t)]
    }
    const [x1, y1] = p(a)
    const [x2, y2] = p(b)
    return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`
  }
  const cover =
    d?.cover_up_from && d.cover_up_until ? `${fmtClock(d.cover_up_from)}–${fmtClock(d.cover_up_until)}` : null
  return (
    <Card title="UV index" subtitle="Now, with today's peak (WHO categories)" action={d && <StaleBadge updatedAt={d.updated_at} stale={d.stale} />}>
      {q.isLoading && <Skeleton className="h-[140px] w-full" />}
      {q.isError && <EmptyState message="Could not load UV." />}
      {d && (d.uv_index === null ? <EmptyState /> : (
        <>
          <svg viewBox="0 0 200 120" className="mx-auto h-auto w-full max-w-[240px]" role="img"
               aria-label={`UV index ${d.uv_index.toFixed(1)}, ${d.category}`}>
            {UV_BANDS.map(([a, b, c]) => (
              <path key={a} d={arc(a + 0.08, b - 0.08)} fill="none" stroke={c} strokeWidth={12} strokeLinecap="butt" />
            ))}
            <g transform={`rotate(${uvAngle(d.uv_index)} ${cx} ${cy})`}>
              <path d={`M ${cx} ${cy - R - 2} l -6 -10 h 12 z`} fill="var(--text)" />
            </g>
            <text x={cx} y={cy - 18} textAnchor="middle" fontSize={30} fontWeight={500} fill="var(--text)">
              {d.uv_index.toFixed(1)}
            </text>
            <text x={cx} y={cy + 2} textAnchor="middle" fontSize={13} fontWeight={500} fill="var(--text-muted)">
              {d.category}
            </text>
          </svg>
          <p className="mt-2 flex items-start gap-2 rounded-full bg-slate-50 px-4 py-2 text-[12px]">
            <Sun aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
            {d.uv_index_max !== null && `Peak today ${d.uv_index_max.toFixed(1)} (${d.max_category}). `}
            {cover ? `Cover up ${cover}.` : 'No cover-up needed today.'}
          </p>
        </>
      ))}
    </Card>
  )
}

// ---------------------------------------------------------------- Current condition

function Segments({ pct, colour }: { pct: number; colour: string }) {
  const n = 30
  const filled = Math.round((Math.max(0, Math.min(100, pct)) / 100) * n)
  return (
    <div className="flex h-3 gap-[2px]" aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} className="flex-1 rounded-[2px]" style={{ background: i < filled ? colour : '#e5e9ed' }} />
      ))}
    </div>
  )
}

export function ConditionGrid({ now, today, loading }: { now: WeatherNowFull | undefined; today: WeatherDay | undefined; loading: boolean }) {
  const tiles = [
    { label: 'Rainfall', value: now?.precipitation, unit: 'mm', icon: Droplets, digits: 1 },
    { label: 'Humidity', value: now?.humidity, unit: '%', icon: Waves, digits: 0 },
    { label: 'Dew point', value: now?.dew_point, unit: '°C', icon: Thermometer, digits: 0 },
    { label: 'Pressure', value: now?.pressure, unit: 'hPa', icon: Gauge, digits: 0 },
  ]
  const swing = today?.temperature_max != null && today.temperature_min != null ? today.temperature_max - today.temperature_min : null
  const rows = [
    { label: 'Cloud cover', value: now?.cloud_cover ?? null, text: (v: number) => `${Math.round(v)}%`, pct: (v: number) => v, colour: '#9fb1c2', note: cloudNote },
    { label: 'Rain chance today', value: today?.precipitation_probability_max ?? null, text: (v: number) => `${Math.round(v)}%`, pct: (v: number) => v, colour: '#3b82f6', note: rainNote },
    { label: 'Day–night swing', value: swing, text: (v: number) => `${Math.round(v)}°C`, pct: (v: number) => (v / 25) * 100, colour: '#f08a3c', note: swingNote },
  ] // prettier-ignore
  return (
    <Card title="Current condition" subtitle={now?.stale ? undefined : 'This hour, Open-Meteo model'} action={now && <StaleBadge updatedAt={now.updated_at} stale={now.stale} />}>
      {loading ? (
        <Skeleton className="h-[260px] w-full" />
      ) : (
        <>
          <dl className="grid grid-cols-2 overflow-hidden rounded-2xl border border-dashed border-slate-200">
            {tiles.map((t, i) => (
              <div key={t.label} className={'flex items-end justify-between p-3 ' + (i % 2 === 0 ? 'border-r border-dashed border-slate-200 ' : '') + (i < 2 ? 'border-b border-dashed border-slate-200' : '')}>
                <div>
                  <dt className="text-[13px] text-ink-muted">{t.label}</dt>
                  <dd className="mt-1 text-[22px] font-medium leading-none">
                    {t.value == null ? <span className="text-[13px] font-normal text-ink-muted">No reading</span> : (
                      <>
                        {t.value.toFixed(t.digits)}
                        <span className="ml-1 text-[12px] font-normal text-ink-muted">{t.unit}</span>
                      </>
                    )}
                  </dd>
                </div>
                <t.icon aria-hidden className="h-6 w-6 text-accent" strokeWidth={1.6} />
              </div>
            ))}
          </dl>
          <ul className="mt-4 space-y-4">
            {rows.map((r) => (
              <li key={r.label}>
                <div className="mb-1.5 flex justify-between text-[14px]">
                  <span>{r.label}</span>
                  <span className="font-medium">{r.value === null ? <span className="text-[12px] font-normal text-ink-muted">No reading</span> : r.text(r.value)}</span>
                </div>
                {r.value !== null && (
                  <>
                    <Segments pct={r.pct(r.value)} colour={r.colour} />
                    <p className="mt-1 text-[11px] text-ink-muted">{r.note(r.value)}</p>
                  </>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

const AQI_SOURCE: Record<string, string> = {
  official: 'CPCB',
  measured: 'CPCB/SPCB stations via OpenAQ',
  cams: 'CAMS model',
}

/** The air side of today, so the weather tab links to it: one number, its source and label. */
export function AirTodayCard({ place }: { place: string }) {
  const q = useAirNow(place)
  const d = q.data
  const estimated = d?.aqi_kind === 'cams'
  return (
    <Card title="Air today" subtitle="India AQI right now" estimated={estimated} as="article">
      {q.isLoading && <Skeleton className="h-12 w-full" />}
      {q.isError && <EmptyState message="Could not load the AQI." />}
      {d && d.aqi === null && <EmptyState message="No AQI reading in the last few hours" />}
      {d && d.aqi !== null && (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-baseline gap-2">
              <span aria-hidden className="h-3 w-3 self-center rounded-full" style={{ background: aqiVar(d.category_key) }} />
              <span className="text-[34px] font-medium leading-none tracking-tight">{d.aqi}</span>
              <span className="text-[14px] font-medium">{d.category}</span>
            </p>
            {estimated ? <EstimatedBadge /> : <MeasuredBadge />}
          </div>
          <p className="mt-2 text-[12px] text-ink-muted">
            {AQI_SOURCE[d.aqi_kind ?? ''] ?? d.source}
            {d.hour && ` · ${formatIstTime(new Date(new Date(d.hour).getTime() + 3_600_000))} IST`}
          </p>
          <Link
            to={{ pathname: '/air', search: `?place=${place}` }}
            className="focus-ring mt-3 inline-flex min-h-touch items-center gap-2 rounded-full bg-slate-100 px-4 text-[13px] font-medium hover:bg-slate-200"
          >
            Open the Air tab <ArrowRight aria-hidden className="h-4 w-4" />
          </Link>
        </>
      )}
    </Card>
  )
}
