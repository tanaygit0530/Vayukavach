import type { AirDay, AirHour, AirMonth } from './api'
import { AQI_LABELS, aqiKey } from './aqi'
import { IST_TZ } from './format'

/** One column of the chart, whatever the mode. */
export interface Column {
  key: string
  label: string // x-axis label (shown selectively)
  showLabel: boolean
  low: number | null // floating bars (10 days); null = from zero
  value: number | null // bar top
  kind: 'measured' | 'shadow' | 'estimated' | 'forecast' | 'outlook' | 'none'
  outlined?: boolean // current month
  isNow?: boolean
  tooltip: string[]
}

const fmtHour = (iso: string) =>
  new Intl.DateTimeFormat('en-IN', { hour: 'numeric', hour12: true, timeZone: IST_TZ })
    .format(new Date(iso))
    .replace(' ', '')
    .toUpperCase()
const fmtDay = (d: string) =>
  new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${d}T00:00:00Z`),
  )
const fmtMonth = (m: string) =>
  new Intl.DateTimeFormat('en-IN', { month: 'short', timeZone: 'UTC' }).format(new Date(`${m}-01T00:00:00Z`))

const cat = (v: number | null) => (v === null ? '' : ` (${AQI_LABELS[aqiKey(v)!]})`)

export function hourlyColumns(hours: AirHour[], now: Date): Column[] {
  const current = hours.findIndex((h) => {
    const start = new Date(h.hour).getTime()
    return now.getTime() >= start && now.getTime() < start + 3600_000
  })
  return hours.map((h, i) => {
    let value: number | null
    let kind: Column['kind']
    const tooltip = [fmtHour(h.hour) + ' IST']
    if (h.is_forecast) {
      value = h.forecast_aqi
      kind = value === null ? 'none' : 'forecast'
      tooltip.push(value === null ? 'No forecast' : `Forecast AQI ${value}${cat(value)} · CAMS, Estimated`)
    } else if (h.official_aqi !== null) {
      value = h.official_aqi
      kind = 'measured'
      tooltip.push(`Official AQI ${value}${cat(value)} · CPCB, Measured`)
      if (h.shadow_aqi !== null) tooltip.push(`Shadow AQI ${h.shadow_aqi} · Estimated`)
    } else if (h.shadow_aqi !== null) {
      value = h.shadow_aqi
      kind = 'shadow'
      tooltip.push('Official reading missing for this hour')
      tooltip.push(
        `Shadow AQI ${value}${cat(value)}` +
          (h.shadow_aqi_low !== null ? ` (${h.shadow_aqi_low}–${h.shadow_aqi_high})` : '') +
          ' · Estimated',
      )
    } else if (h.estimated_aqi !== null) {
      value = h.estimated_aqi
      kind = 'estimated'
      tooltip.push('No station reading for this hour')
      tooltip.push(`Model AQI ${value}${cat(value)} · CAMS, Estimated`)
    } else {
      value = null
      kind = 'none'
      tooltip.push('No reading for this hour')
    }
    return {
      key: h.hour,
      label: fmtHour(h.hour),
      showLabel: i % 3 === 0,
      low: null,
      value,
      kind,
      isNow: i === current,
      tooltip,
    }
  })
}

export function dailyColumns(days: AirDay[]): Column[] {
  return days.map((d) => ({
    key: d.date,
    label: fmtDay(d.date),
    showLabel: true,
    low: d.low,
    value: d.high,
    kind: d.is_outlook ? 'outlook' : d.available ? 'forecast' : 'none',
    tooltip: [
      fmtDay(d.date),
      d.available && d.low !== null
        ? `AQI ${d.low}–${d.high}${cat(d.high)} · CAMS forecast, Estimated`
        : d.is_outlook
          ? 'Outlook not available yet'
          : 'No forecast',
    ],
  }))
}

export function monthlyColumns(months: AirMonth[]): Column[] {
  return months.map((m) => ({
    key: m.month,
    label: fmtMonth(m.month),
    showLabel: true,
    low: null,
    value: m.avg_aqi,
    kind: m.avg_aqi === null ? 'none' : 'measured',
    outlined: m.is_current,
    tooltip: [
      fmtMonth(m.month) + ' ' + m.month.slice(0, 4),
      m.avg_aqi === null ? 'No data stored for this month' : `Average AQI ${m.avg_aqi}${cat(m.avg_aqi)} · ${m.days} days`,
    ],
  }))
}

