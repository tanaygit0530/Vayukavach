import clsx from 'clsx'
import { Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { AQI_KEYS, AQI_LABELS, aqiKey, aqiVar, LIGHT_KEYS } from '../../lib/aqi'
import { type Column, dailyColumns, hourlyColumns, monthlyColumns } from '../../lib/aqiColumns'
import { useAirDaily, useAirHourly, useAirMonthly } from '../../lib/queries'
import { StaleBadge } from '../ui/Badges'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'
import { Tabs } from '../ui/Tabs'

export type Mode = 'hourly' | 'daily' | 'monthly'

const W = 720
const H = 330
const PAD = { left: 34, right: 8, top: 12, bottom: 28 }
const PLOT_H = H - PAD.top - PAD.bottom
const Y_MAX = 500
const y = (v: number) => PAD.top + PLOT_H * (1 - Math.min(v, Y_MAX) / Y_MAX)

function Bars({ columns, mode }: { columns: Column[]; mode: Mode }) {
  const [hover, setHover] = useState<number | null>(null)
  const n = columns.length
  const step = (W - PAD.left - PAD.right) / n
  const barW = Math.max(6, Math.min(mode === 'hourly' ? 12 : 20, step * 0.45))
  const nowIdx = columns.findIndex((c) => c.isNow)
  return (
    <div className="relative -mx-1 overflow-x-auto px-1">
      <div className="relative min-w-[560px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="AQI chart">
        {/* recessive grid + y axis */}
        {[0, 100, 200, 300, 400, 500].map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e3e8ec" strokeWidth={1} />
            <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize={10} fill="var(--text-muted)">
              {t}
            </text>
          </g>
        ))}
        {nowIdx >= 0 && (
          <g>
            <line
              x1={PAD.left + step * (nowIdx + 0.5)}
              x2={PAD.left + step * (nowIdx + 0.5)}
              y1={PAD.top - 4}
              y2={PAD.top + PLOT_H}
              stroke="var(--text)"
              strokeWidth={1.5}
            />
            <text
              x={PAD.left + step * (nowIdx + 0.5) + 4}
              y={PAD.top + 6}
              fontSize={10}
              fontWeight={600}
              fill="var(--text)"
            >
              Now
            </text>
          </g>
        )}
        {columns.map((c, i) => {
          const cx = PAD.left + step * (i + 0.5)
          const x = cx - barW / 2
          const key = aqiKey(c.value)
          const fill = aqiVar(key)
          const dashed = c.kind === 'shadow' || c.kind === 'estimated' || c.kind === 'forecast' || c.kind === 'outlook'
          const faded = c.kind === 'forecast' || c.kind === 'outlook'
          const top = c.value !== null ? y(c.value) : null
          const bottom = c.low !== null ? y(c.low) : y(0)
          return (
            <g key={c.key}>
              {/* hit target: the full column */}
              <rect
                x={PAD.left + step * i}
                y={PAD.top}
                width={step}
                height={PLOT_H}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
              {top !== null ? (
                <rect
                  x={x}
                  y={top}
                  width={barW}
                  height={Math.max(2, bottom - top)}
                  rx={4}
                  fill={c.kind === 'shadow' || c.kind === 'estimated' ? 'white' : fill}
                  fillOpacity={faded ? 0.45 : 1}
                  stroke={
                    c.kind === 'shadow' || c.kind === 'estimated'
                      ? fill
                      : key && LIGHT_KEYS.has(key)
                        ? 'rgba(23,33,43,0.28)'
                        : 'none'
                  }
                  strokeWidth={c.kind === 'shadow' || c.kind === 'estimated' ? 2 : 1}
                  strokeDasharray={dashed ? '4 3' : undefined}
                  pointerEvents="none"
                />
              ) : (
                c.kind === 'outlook' || c.kind === 'none' ? (
                  <line
                    x1={cx - barW / 2}
                    x2={cx + barW / 2}
                    y1={y(0) - 1}
                    y2={y(0) - 1}
                    stroke="#b8c1c9"
                    strokeWidth={2}
                    strokeDasharray="3 2"
                    pointerEvents="none"
                  />
                ) : null
              )}
              {c.mid != null && top !== null && (
                <line
                  x1={x - 3}
                  x2={x + barW + 3}
                  y1={y(c.mid)}
                  y2={y(c.mid)}
                  stroke="var(--text)"
                  strokeWidth={2}
                  strokeLinecap="round"
                  pointerEvents="none"
                />
              )}
              {c.outlined && top !== null && (
                <rect
                  x={x - 3}
                  y={top - 3}
                  width={barW + 6}
                  height={Math.max(2, bottom - top) + 3}
                  rx={6}
                  fill="none"
                  stroke="var(--text)"
                  strokeWidth={1.5}
                  pointerEvents="none"
                />
              )}
              {c.showLabel && (
                <text
                  x={cx}
                  y={H - 8}
                  textAnchor="middle"
                  fontSize={10}
                  fontWeight={c.isNow ? 600 : 400}
                  fill={c.isNow ? 'var(--text)' : 'var(--text-muted)'}
                >
                  {c.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 w-max max-w-[240px] -translate-x-1/2 rounded-xl bg-white px-3 py-2 text-[12px] shadow-card ring-1 ring-slate-200"
          style={{
            left: `${((PAD.left + step * (hover + 0.5)) / W) * 100}%`,
            top: 0,
          }}
        >
          {columns[hover].tooltip.map((line, i) => (
            <p key={i} className={i === 0 ? 'font-medium text-ink' : 'text-ink-muted'}>
              {line}
            </p>
          ))}
        </div>
      )}
      </div>
    </div>
  )
}

function DataTable({ columns, caption }: { columns: Column[]; caption: string }) {
  return (
    <div className="max-h-[260px] overflow-auto">
      <table className="w-full text-left text-[12px]">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-white text-ink-muted">
          <tr>
            <th className="py-1 font-medium">Time</th>
            <th className="py-1 font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((c) => (
            <tr key={c.key} className="border-t border-slate-100">
              <td className="py-1">{c.tooltip[0]}</td>
              <td className="py-1 text-ink-muted">{c.tooltip.slice(1).join(' · ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Legend({ mode }: { mode: Mode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-muted">
      {AQI_KEYS.map((k) => (
        <span key={k} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="h-2.5 w-2.5 rounded-[3px]"
            style={{ background: aqiVar(k), boxShadow: LIGHT_KEYS.has(k) ? 'inset 0 0 0 1px rgba(23,33,43,.28)' : undefined }}
          />
          {AQI_LABELS[k]}
        </span>
      ))}
      {mode === 'hourly' && (
        <>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-2.5 w-2.5 rounded-[3px] border-2 border-dashed border-ink-muted bg-white" />
            Shadow (reading missing)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-2.5 w-2.5 rounded-[3px] border border-dashed border-ink-muted bg-slate-300/60" />
            Forecast
          </span>
        </>
      )}
      {mode === 'daily' && (
        <>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-3 bg-ink" />
            Most likely
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-2.5 w-2.5 rounded-[3px] border border-dashed border-ink-muted bg-slate-300/60" />
            Forecast range (outlook days fainter)
          </span>
        </>
      )}
    </div>
  )
}

const NOTES: Record<Mode, string> = {
  hourly: 'Past hours: CPCB official AQI (Measured); dashed outline = official reading missing, shadow estimate shown. Later hours: CAMS forecast (Estimated).',
  daily: 'Bars: likely low–high; dark tick: most likely value. Days 1–5: CAMS forecast (bias-corrected when the model beats raw CAMS). Days 6–10: outlook model, lower confidence. All Estimated.',
  monthly: 'Average daily AQI from stored station data; current month outlined. Months without stored data are left empty.',
}

export function AqiChart({ place }: { place: string }) {
  const [mode, setMode] = useState<Mode>('hourly')
  const [table, setTable] = useState(false)
  const hourly = useAirHourly(place)
  const daily = useAirDaily(place, mode === 'daily')
  const monthly = useAirMonthly(place, mode === 'monthly')
  const query = mode === 'hourly' ? hourly : mode === 'daily' ? daily : monthly

  const columns = useMemo(() => {
    if (mode === 'hourly' && hourly.data) return hourlyColumns(hourly.data.hours, new Date())
    if (mode === 'daily' && daily.data) return dailyColumns(daily.data.days)
    if (mode === 'monthly' && monthly.data) return monthlyColumns(monthly.data.months)
    return null
  }, [mode, hourly.data, daily.data, monthly.data])

  const empty = columns !== null && columns.every((c) => c.value === null)
  const meta = query.data

  return (
    <Card
      title="Air Quality Index"
      subtitle="India AQI (0–500). Hover a bar for details."
      action={
        <div className="flex items-center gap-2">
          <Tabs
            label="Chart period"
            value={mode}
            onChange={setMode}
            tabs={[
              { id: 'hourly', label: 'Hourly' },
              { id: 'daily', label: '10 days' },
              { id: 'monthly', label: 'Monthly' },
            ]}
          />
          <button
            type="button"
            aria-pressed={table}
            aria-label={table ? 'Show chart' : 'Show as table'}
            title={table ? 'Show chart' : 'Show as table'}
            onClick={() => setTable((t) => !t)}
            className={clsx(
              'focus-ring grid h-[44px] w-[44px] place-items-center rounded-full',
              table ? 'bg-ink text-white' : 'bg-slate-100 text-ink-muted hover:text-ink',
            )}
          >
            <Table2 aria-hidden className="h-4 w-4" />
          </button>
        </div>
      }
      className="lg:col-span-2"
    >
      <Legend mode={mode} />
      {query.isLoading && <Skeleton className="h-[220px] w-full" />}
      {query.isError && <EmptyState message="Could not load the AQI series." />}
      {columns && empty && <EmptyState message="No AQI data stored for this period yet." />}
      {columns && !empty && (table ? <DataTable columns={columns} caption={`AQI ${mode}`} /> : <Bars columns={columns} mode={mode} />)}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <p className="text-[11px] text-ink-muted">{NOTES[mode]}</p>
        {meta && mode === 'hourly' && <StaleBadge updatedAt={meta.updated_at} stale={meta.stale} />}
      </div>
    </Card>
  )
}
