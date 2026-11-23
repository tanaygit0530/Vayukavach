/** Typed client for the VayuKavach API (/api/v1). Every response carries Meta. */

export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000')
  .replace(/\/$/, '')

export type Label = 'measured' | 'estimated' | 'mixed' | null

export interface Meta {
  source: string
  updated_at: string | null
  label: Label
  stale: boolean
}

export interface District {
  id: string
  name: string
  state: string
  lat: number
  lon: number
}

export interface PlaceSummary {
  id: string
  name: string
  state: string
  aqi: number | null
  category: string | null
  category_key: string | null
  aqi_label: Label
  aqi_hour: string | null
  temperature: number | null
  today_high: number | null
  today_low: number | null
  condition: string | null
}

export interface PlaceResult {
  name: string | null
  state: string | null
  district: string | null
  lat: number
  lon: number
  population: number | null
  covered_district: string | null
  distance_km: number | null
}

export interface AirNow extends Meta {
  district: string
  aqi: number | null
  category: string | null
  category_key: string | null
  main_pollutant: string | null
  aqi_kind: 'official' | 'measured' | 'cams' | null
  hour: string | null
  stations_reporting: number | null
  visibility_m: number | null
  completeness_pct: number | null
  shadow_aqi: number | null
  shadow_aqi_low: number | null
  shadow_aqi_high: number | null
}

export interface WeatherNow extends Meta {
  district: string
  temperature: number | null
  apparent_temperature: number | null
  humidity: number | null
  condition: string | null
  weather_code: number | null
  today_high: number | null
  today_low: number | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}/api/v1${path}`)
  Object.entries(params ?? {}).forEach(([k, v]) => url.searchParams.set(k, v))
  const response = await fetch(url)
  if (!response.ok) {
    let detail = response.statusText
    try {
      detail = (await response.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export interface AirHour {
  hour: string
  official_aqi: number | null
  shadow_aqi: number | null
  shadow_aqi_low: number | null
  shadow_aqi_high: number | null
  estimated_aqi: number | null
  forecast_aqi: number | null
  is_forecast: boolean
  official_missing: boolean
}

export interface AirDay {
  date: string
  low: number | null
  high: number | null
  is_outlook: boolean
  available: boolean
  label: string
}

export interface AirMonth {
  month: string
  avg_aqi: number | null
  days: number
  is_current: boolean
}

export interface PollutantValue {
  pollutant: string
  value: number | null
  unit: string
  sub_index: number | null
  label: 'measured' | 'estimated' | null
  stations: number
}

export interface Co2 {
  value: number
  unit: string
  hour: string
  label: string
  note: string
}

export interface StationPin {
  id: number
  name: string
  lat: number
  lon: number
  aqi: number | null
  category: string | null
  category_key: string | null
  main_pollutant: string | null
  status: 'measured' | 'estimated' | 'silent'
  last_seen_at: string | null
}

export interface Wind extends Meta {
  speed_kmh: number | null
  gusts_kmh: number | null
  direction_deg: number | null
  direction_compass: string | null
  boundary_layer_m: number | null
  note: string | null
}

export interface Advice extends Meta {
  aqi: number | null
  category: string | null
  category_key: string | null
  health_impact: string | null
  advice_source: string
}

export interface MapCell {
  lat: number
  lon: number
  pm25: number | null
  pm25_sub_index: number | null
  category_key: string | null
}
