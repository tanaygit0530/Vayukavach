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
