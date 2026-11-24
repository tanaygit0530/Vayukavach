import clsx from 'clsx'
import { ArrowRight, Droplets, Flame, Info, Sun, Thermometer } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { HeatDayOut, HeatHourOut, HeatReport } from '../../lib/api'
import { useUv } from '../../lib/queries'
import { arcSegments, clock, HEAT_THEME, isLevel, LEVEL_NAMES, windowsText, WORK_END, WORK_START } from '../../lib/heat'
import { fmtClock } from '../../lib/weather'
import { Skeleton } from '../ui/Skeleton'

export function HeatCard({ title, subtitle, children, className, action }: {
  title: string; subtitle?: string; children: ReactNode; className?: string; action?: ReactNode
}) {
  return (
    <section aria-label={title} className={clsx('heat-card p-5', className)}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-medium">{title}</h2>
          {subtitle && <p className="mt-0.5 text-[13px] text-white/80">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  )
}

export function LevelPill({ level, small }: { level: string | null; small?: boolean }) {
  if (!isLevel(level)) return <span className="text-[12px] text-white/75">No data</span>
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded-full bg-white/15 font-medium', small ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-[13px]')}>
      <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: HEAT_THEME[level].accent }} />
      {LEVEL_NAMES[level]}
    </span>
  )
}

const DarkNote = ({ children }: { children: ReactNode }) => (
  <p className="mt-3 flex items-start gap-2 rounded-2xl bg-white/10 px-3 py-2 text-[12px] text-white/90">
    <Info aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
    <span>{children}</span>
  </p>
)

// ---------------------------------------------------------------- hero

export function HeatHero({ data, district, loading }: { data: HeatReport | undefined; district: string; loading: boolean }) {
  const value = data?.feels_like
  return (
    <section aria-label="Heat now" className="flex flex-col items-center px-2 py-6 text-center text-white">
      {loading ? (
        <Skeleton className="h-[120px] w-[220px] bg-white/20" />
      ) : value == null ? (
        <p className="text-[18px]">No reading for this hour</p>
      ) : (
        <p className="font-dot leading-none" aria-label={`Feels like ${Math.round(value)} degrees Celsius`}>
          <span className="text-[112px] tracking-[0.04em] md:text-[140px]">{Math.round(value)}</span>
          <span className="align-top text-[40px]">°</span>
        </p>
      )}
      <p className="mt-2 text-[15px] text-white/85">Feels like</p>
      <p className="mt-3 text-[22px] font-semibold">{data?.level_name ?? '–'}</p>
      <p className="text-[15px] text-white/85">{district}</p>
      {data?.instruction && <p className="mt-3 max-w-[520px] text-[16px] font-medium">{data.instruction}</p>}
      {data && (
        <p className="mt-2 text-[12px] text-white/75">
          Open-Meteo model (Estimated) · levels are a draft, to be aligned with the district heat action plan
        </p>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- safe work hours (day arc)

export function SafeWorkArc({ data, now = new Date() }: { data: HeatReport; now?: Date }) {
  const segs = arcSegments(data.hourly)
  const R = 120
  const cx = 150
  const cy = 140
  const n = WORK_END - WORK_START
  const point = (t: number) => [cx - R * Math.cos(Math.PI * t), cy - R * Math.sin(Math.PI * t)] as const
  const istHour = Number(new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(now))
  const istMin = Number(new Intl.DateTimeFormat('en-GB', { minute: '2-digit', timeZone: 'Asia/Kolkata' }).format(now))
  const t = (istHour + istMin / 60 - WORK_START) / n
  const [dx, dy] = point(Math.min(1, Math.max(0, t)))
  const inDay = t >= 0 && t <= 1
  return (
    <HeatCard title="Safe work hours" subtitle="Today, 6 AM–7 PM. Solid = below Caution; dotted = take care.">
      <svg viewBox="-16 -16 332 182" className="mx-auto h-auto w-full max-w-[360px]" role="img"
           aria-label={`Safe work hours today: ${windowsText(data.safe_work_windows)}`}>
        {segs.map((s, i) => {
          const [x1, y1] = point(i / n + 0.004)
          const [x2, y2] = point((i + 1) / n - 0.004)
          const colour = s.level ? HEAT_THEME[s.level].accent : 'rgba(255,255,255,.25)'
          return (
            <path key={s.hour} d={`M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`} fill="none"
                  stroke={s.safe ? '#ffffff' : colour} strokeWidth={s.safe ? 10 : 8}
                  strokeLinecap="round" strokeDasharray={s.safe ? undefined : '2 7'} />
          )
        })}
        {[6, 9, 12, 15, 19].map((h) => {
          const [x, y] = point((h - WORK_START) / n)
          const [lx, ly] = [cx + (x - cx) * 1.17, cy + (y - cy) * 1.17]
          return <text key={h} x={lx} y={ly + 4} textAnchor="middle" fontSize={10} fill="rgba(255,255,255,.85)">{clock(h)}</text>
        })}
        {inDay && <circle cx={dx} cy={dy} r={7} fill="#fff" stroke="rgba(0,0,0,.35)" strokeWidth={2} />}
        <text x={cx} y={cy - 30} textAnchor="middle" fontSize={11} fill="rgba(255,255,255,.85)">Safe windows</text>
        <text x={cx} y={cy - 10} textAnchor="middle" fontSize={15} fontWeight={600} fill="#fff">
          {data.safe_work_windows.length ? `${data.safe_work_windows.length} today` : 'None today'}
        </text>
      </svg>
      <p className="mt-2 text-center text-[14px] font-medium">{windowsText(data.safe_work_windows)}</p>
    </HeatCard>
  )
}

// ---------------------------------------------------------------- hourly strip

export function HourlyStrip({ hours, now = new Date() }: { hours: HeatHourOut[]; now?: Date }) {
  // Hours that start after now: the current hour is the hero number.
  const list = hours.filter((h) => new Date(h.hour).getTime() > now.getTime())
  return (
    <HeatCard title="Hour by hour" subtitle="Level, temperature and feels-like for the rest of today" className="flex flex-col lg:col-span-2">
      {list.length === 0 ? (
        <p className="text-[13px] text-white/80">No more hours today. See the 10-day forecast.</p>
      ) : (
        // columns share the full width (and the card's height), scrolling only when there are many hours
        <ol className="grid flex-1 auto-cols-[minmax(84px,1fr)] grid-flow-col gap-2 overflow-x-auto pb-1">
          {list.map((h) => (
            <li key={h.hour} className="flex flex-col items-center justify-center gap-2 rounded-2xl bg-white/10 px-2 py-3">
              <span className="text-[12px] text-white/85">{clock(h.local_hour)}</span>
              <LevelPill level={h.level} small />
              <span className="text-[24px] font-medium">{h.temperature == null ? '–' : `${Math.round(h.temperature)}°`}</span>
              <span className="text-[11px] text-white/80">feels {h.feels_like == null ? '–' : `${Math.round(h.feels_like)}°`}</span>
            </li>
          ))}
        </ol>
      )}
    </HeatCard>
  )
}

// ---------------------------------------------------------------- 10-day

export function HeatForecast({ days }: { days: HeatDayOut[] }) {
  const list = days.slice(0, 10) // today + 9 days: today's range is not shown elsewhere on this tab
  const lo = Math.min(...list.map((d) => d.temperature_min))
  const hi = Math.max(...list.map((d) => d.temperature_max))
  const span = Math.max(1, hi - lo)
  const day = (date: string) =>
    new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`))
  return (
    <HeatCard title="Heat forecast" subtitle="Daily temperature range and the day's highest level" className="flex flex-col">
      {list.length === 0 ? (
        <p className="text-[13px] text-white/80">No forecast stored yet.</p>
      ) : (
        <ul className="flex flex-1 flex-col justify-between divide-y divide-white/10">
          {list.map((d) => (
            <li key={d.date} className="grid grid-cols-[58px_84px_34px_1fr_34px] items-center gap-2 py-2 text-[13px]">
              <span className="text-white/85">{d.is_forecast ? day(d.date) : 'Today'}</span>
              <LevelPill level={d.level} small />
              <span className="text-right text-white/85">{Math.round(d.temperature_min)}°</span>
              <span className="relative h-[6px] rounded-full bg-white/15" aria-hidden>
                <span className="absolute inset-y-0 rounded-full bg-white/85"
                      style={{ left: `${((d.temperature_min - lo) / span) * 100}%`, right: `${100 - ((d.temperature_max - lo) / span) * 100}%` }} />
              </span>
              <span className="font-medium">{Math.round(d.temperature_max)}°</span>
            </li>
          ))}
        </ul>
      )}
    </HeatCard>
  )
}

// ---------------------------------------------------------------- heat stress + UV + what to do

export function HeatStress({ data }: { data: HeatReport }) {
  const rows = [
    { icon: Thermometer, label: 'Air temperature', value: data.temperature, unit: '°C' },
    { icon: Flame, label: 'Heat index', value: data.heat_index, unit: '°C' },
    { icon: Droplets, label: 'Wet-bulb', value: data.wet_bulb, unit: '°C' },
    { icon: Droplets, label: 'Humidity', value: data.humidity, unit: '%' },
  ]
  return (
    <HeatCard title="Heat stress" subtitle="Heat index (NWS) and wet-bulb (Stull 2011)" className="flex flex-col">
      {/* the four tiles grow with the card instead of leaving a gap under them */}
      <dl className="grid flex-1 auto-rows-fr grid-cols-2 gap-3">
        {rows.map((r) => (
          <div key={r.label} className="flex flex-col justify-center gap-3 rounded-2xl bg-white/10 p-4">
            <dt className="flex items-center gap-1.5 text-[12px] text-white/85"><r.icon aria-hidden className="h-3.5 w-3.5" />{r.label}</dt>
            <dd className="text-[36px] font-medium leading-none tracking-tight">{r.value == null ? <span className="text-[13px] font-normal">No reading</span> : `${Math.round(r.value)}${r.unit}`}</dd>
          </div>
        ))}
      </dl>
      <DarkNote>Wet-bulb near 31 °C is the point where sweating stops cooling the body during work.</DarkNote>
    </HeatCard>
  )
}

export function UvCard({ place }: { place: string }) {
  const q = useUv(place)
  const d = q.data
  return (
    <HeatCard title="UV index" subtitle="Now and today's peak">
      {q.isLoading ? <Skeleton className="h-16 w-full bg-white/20" /> : !d || d.uv_index == null ? (
        <p className="text-[13px] text-white/80">No reading for this hour</p>
      ) : (
        <>
          <p className="flex items-baseline gap-2"><Sun aria-hidden className="h-5 w-5" />
            <span className="text-[34px] font-medium">{d.uv_index.toFixed(1)}</span>
            <span className="text-[14px] text-white/85">{d.category}</span></p>
          <p className="mt-1 text-[13px] text-white/85">
            Peak {d.uv_index_max?.toFixed(1) ?? '–'} ({d.max_category ?? '–'})
            {d.cover_up_from && d.cover_up_until && ` · cover up ${fmtClock(d.cover_up_from)}–${fmtClock(d.cover_up_until)}`}
          </p>
        </>
      )}
    </HeatCard>
  )
}

export function WhatToDo({ data, place }: { data: HeatReport; place: string }) {
  return (
    <HeatCard title="What to do today" subtitle={`For the day's highest level: ${data.worst_level_today ? LEVEL_NAMES[data.worst_level_today as keyof typeof LEVEL_NAMES] ?? '–' : '–'}`}>
      <ul className="space-y-2 text-[14px]">
        {data.tips.map((tip) => (
          <li key={tip} className="flex gap-2"><span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-white" />{tip}</li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-white/75">{data.tips_source}</p>
      <Link to={{ pathname: '/finder', search: `?place=${place}&goal=heat` }}
            className="mt-4 inline-flex min-h-touch items-center gap-2 rounded-full bg-white px-5 text-[14px] font-medium text-ink outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black">
        Find cooler places <ArrowRight aria-hidden className="h-4 w-4" />
      </Link>
    </HeatCard>
  )
}
