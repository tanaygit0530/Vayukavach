import type { WeatherDay, WeatherHour } from './api'
import { IST_TZ } from './format'

export const istHour = (iso: string): number =>
  Number(new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hourCycle: 'h23', timeZone: IST_TZ }).format(new Date(iso)))

export const istDate = (iso: string): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: IST_TZ }).format(new Date(iso)) // YYYY-MM-DD

export const fmtClock = (iso: string | null): string | null =>
  iso
    ? new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: IST_TZ })
        .format(new Date(iso))
        .toUpperCase()
    : null

export const fmtHourShort = (h: number): string => `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? 'AM' : 'PM'}`

export function fmtDuration(seconds: number | null): string | null {
  if (seconds === null) return null
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return `${h}h ${String(m).padStart(2, '0')}m`
}

export interface TrendPoint {
  hour: number // IST clock hour
  temp: number | null
  isNow: boolean
  isForecast: boolean
}

/** Today's 7 AM-7 PM IST hours (13 points). */
export function trendPoints(hours: WeatherHour[], now: Date, from = 7, to = 19): TrendPoint[] {
  const today = istDate(now.toISOString())
  const nowHour = istHour(now.toISOString())
  const byHour = new Map(
    hours.filter((h) => istDate(h.hour) === today).map((h) => [istHour(h.hour), h] as const),
  )
  return Array.from({ length: to - from + 1 }, (_, i) => {
    const hour = from + i
    const h = byHour.get(hour)
    return { hour, temp: h?.temperature ?? null, isNow: hour === nowHour, isForecast: h?.is_forecast ?? hour > nowHour }
  })
}

/** Fraction of the way from sunrise to sunset (clamped 0..1), or null at night. */
export function sunFraction(sunrise: string | null, sunset: string | null, now: Date): number | null {
  if (!sunrise || !sunset) return null
  const a = new Date(sunrise).getTime()
  const b = new Date(sunset).getTime()
  const t = now.getTime()
  if (t < a || t > b) return null
  return (t - a) / (b - a)
}

export const UV_MAX = 12
/** Gauge angle in degrees: -90 (left, UV 0) to +90 (right, UV 12+). */
export const uvAngle = (uv: number): number => -90 + (Math.min(Math.max(uv, 0), UV_MAX) / UV_MAX) * 180

export function cloudNote(pct: number): string {
  if (pct < 20) return 'Mostly clear sky'
  if (pct < 60) return 'Partly cloudy'
  return 'Mostly cloudy'
}

export function rainNote(pct: number): string {
  if (pct < 20) return 'Rain unlikely today'
  if (pct < 50) return 'Some chance of rain today'
  return 'Rain likely today: carry an umbrella'
}

export function swingNote(deg: number): string {
  if (deg >= 12) return 'Large day–night swing: keep a layer for the evening'
  if (deg >= 7) return 'Moderate swing between day and night'
  return 'Small swing between day and night'
}

const csvCell = (v: unknown): string => {
  if (v === null || v === undefined) return ''
  const s = String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** One table, `kind` = hourly | daily, union of columns. Missing values stay empty, never 0. */
export function weatherCsv(place: string, hours: WeatherHour[], days: WeatherDay[]): string {
  const cols = [
    'kind', 'place', 'time_ist', 'temperature_c', 'apparent_temperature_c', 'humidity_pct',
    'dew_point_c', 'pressure_hpa', 'cloud_cover_pct', 'precipitation_mm', 'precipitation_probability_pct',
    'uv_index', 'wind_speed_kmh', 'condition', 'temperature_min_c', 'temperature_max_c', 'is_forecast',
    'source',
  ] // prettier-ignore
  const ist = (iso: string) =>
    new Intl.DateTimeFormat('sv-SE', { dateStyle: 'short', timeStyle: 'short', timeZone: IST_TZ }).format(new Date(iso))
  const rows = [
    ...hours.map((h) => [
      'hourly', place, ist(h.hour), h.temperature, h.apparent_temperature, h.humidity, h.dew_point, h.pressure,
      h.cloud_cover, h.precipitation, h.precipitation_probability, h.uv_index, h.wind_speed, h.condition, '', '',
      h.is_forecast, 'Open-Meteo (CC BY 4.0), model values',
    ]), // prettier-ignore
    ...days.map((d) => [
      'daily', place, d.date, '', '', '', '', '', '', d.precipitation_sum,
      d.precipitation_probability_max, d.uv_index_max, '', d.condition, d.temperature_min, d.temperature_max,
      d.is_forecast, 'Open-Meteo (CC BY 4.0), model values',
    ]), // prettier-ignore
  ]
  return [cols, ...rows].map((r) => r.map(csvCell).join(',')).join('\n') + '\n'
}
