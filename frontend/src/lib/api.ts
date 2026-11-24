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
  /** Machine-readable reason, when the API sends `detail: {code, message}`. */
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}/api/v1${path}`)
  Object.entries(params ?? {}).forEach(([k, v]) => url.searchParams.set(k, v))
  const response = await fetch(url)
  if (!response.ok) {
    let detail = response.statusText
    let code: string | undefined
    try {
      const d = (await response.json()).detail
      if (d && typeof d === 'object') {
        detail = d.message ?? detail
        code = d.code
      } else if (typeof d === 'string') detail = d
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail, code)
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
  median: number | null
  is_outlook: boolean
  available: boolean
  label: string
  method: 'cams_corrected' | 'cams_raw' | 'outlook' | null
  model_version: string | null
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

export interface WeatherFields {
  temperature: number | null
  apparent_temperature: number | null
  humidity: number | null
  dew_point: number | null
  wind_speed: number | null
  wind_gusts: number | null
  wind_direction: number | null
  pressure: number | null
  cloud_cover: number | null
  precipitation: number | null
  precipitation_probability: number | null
  visibility: number | null
  uv_index: number | null
  weather_code: number | null
  boundary_layer_height: number | null
  condition: string | null
}

export interface WeatherNowFull extends Meta, WeatherFields {
  district: string
  hour: string | null
  today_high: number | null
  today_low: number | null
  wind_direction_compass: string | null
  feels_like_reason: string | null
  note: string
}

export interface WeatherHour extends WeatherFields {
  hour: string
  is_forecast: boolean
}

export interface WeatherDay {
  date: string
  temperature_min: number | null
  temperature_max: number | null
  apparent_temperature_max: number | null
  weather_code: number | null
  condition: string | null
  precipitation_sum: number | null
  precipitation_probability_max: number | null
  uv_index_max: number | null
  is_forecast: boolean
}

export interface SunDay {
  date: string
  sunrise: string | null
  sunset: string | null
  daylight_seconds: number | null
}

export interface Uv extends Meta {
  uv_index: number | null
  category: string | null
  uv_index_max: number | null
  max_category: string | null
  cover_up_from: string | null
  cover_up_until: string | null
}

export interface HeatSummary extends Meta {
  level: string | null
  level_name: string | null
}

export interface HeatHourOut {
  hour: string
  local_hour: number
  temperature: number | null
  feels_like: number | null
  heat_index: number | null
  wet_bulb: number | null
  level: string | null
}

export interface HeatDayOut {
  date: string
  temperature_min: number
  temperature_max: number
  heat_index_max: number
  wet_bulb_max: number
  level: string | null
  is_forecast: boolean
}

export interface HeatReport extends Meta {
  district: string
  hour: string | null
  temperature: number | null
  humidity: number | null
  feels_like: number | null
  heat_index: number | null
  wet_bulb: number | null
  level: string | null
  level_name: string | null
  instruction: string | null
  worst_level_today: string | null
  safe_work_windows: { from_hour: number; to_hour: number }[]
  hourly: HeatHourOut[]
  daily: HeatDayOut[]
  tips: string[]
  tips_source: string
  thresholds_status: string
}

export interface SectorShare {
  sector: string
  label: string
  share_pct: number
  published_pct: number
}

export interface Sources extends Meta {
  district: string
  kind: 'daily' | 'study' | null
  date: string | null
  sectors: SectorShare[]
  source_name: string | null
  source_url: string | null
  source_year: number | null
  published_sum: number | null
  note: string | null
}

export type Goal = 'air' | 'heat'
export type FinderMode = 'nearby' | 'daytrip' | 'vacation'

export interface FinderPlace {
  id: string
  name: string
  state: string | null
  lat: number
  lon: number
  kind: 'station' | 'town' | 'hill_station'
  distance_km: number
  approx_minutes: number
  value: number
  unit: string
  value_label: 'measured' | 'estimated'
  value_source: string
  category: string | null
  category_key: string | null
  forecast: { date: string; value: number }[]
  forecast_label: string
  better_by: number | null
  score: number
}

export interface FinderResult extends Meta {
  goal: Goal
  mode: FinderMode
  radius_km: number | null
  origin: { name: string; lat: number; lon: number; value: number | null }
  places: FinderPlace[]
  precautions: { for: string; text: string; source: string }[]
  empty_reason: string | null
  note: string
}

export interface RouteResult extends Meta {
  distance_km: number
  duration_min: number
  geometry: [number, number][]
  maps_url: string
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = response.statusText
    let code: string | undefined
    try {
      const d = (await response.json()).detail
      if (d && typeof d === 'object') {
        detail = d.message ?? detail
        code = d.code
      } else if (typeof d === 'string') detail = d
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail, code)
  }
  return response.json() as Promise<T>
}

export interface ChatSource {
  source: string
  time: string | null
  label: 'measured' | 'estimated' | null
  tool: string | null
}

export interface ChatReply {
  answer: string
  sources: ChatSource[]
  refused: boolean
  language: 'en' | 'hi' | 'mr'
  engine: 'gemini' | 'ollama' | 'rules' | 'scope'
}

export interface AlertChannels {
  email: boolean
  sms: boolean
  whatsapp: boolean
  whatsapp_join: string | null
  whatsapp_number: string | null
}

export interface AlertSubscribeReply {
  id: number
  status: 'code_sent' | 'already_subscribed'
  sent_to: string
}

export interface AlertVerifyReply {
  verified: boolean
  channel: string
  sent_to: string
  place: string
  daily: boolean
  instant: boolean
}

export interface GapReport extends Meta {
  district: string
  date: string
  completeness_pct: number | null
  gap_bias: {
    flagged: boolean
    polluted_hours_missing_pct: number | null
    clean_hours_missing_pct: number | null
    difference_pp: number | null
  } | null
  silent_stations: { station_id: number; name: string; from: string; to: string }[]
  city_silent_hours: string[]
  readings_near_limit: {
    station_id: number
    name: string | null
    hour: string
    pollutant: string
    value: number | null
    at_or_over_999: boolean
  }[]
  stations: {
    station_id: number
    name: string
    pollutant: string
    expected: number
    received: number
    excluded: number
    pct: number
    longest_gap_hours: number
  }[]
  wording: string
}

export function apiUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${API_BASE}/api/v1${path}`)
  for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, v)
  return url.toString()
}
