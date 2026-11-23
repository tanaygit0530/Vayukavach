import { useQuery } from '@tanstack/react-query'

import {
  apiGet,
  type Advice,
  type AirDay,
  type AirHour,
  type AirMonth,
  type AirNow,
  type Co2,
  type HeatReport,
  type HeatSummary,
  type SunDay,
  type Uv,
  type WeatherDay,
  type WeatherHour,
  type WeatherNowFull,
  type MapCell,
  type PollutantValue,
  type StationPin,
  type Wind,
  type District,
  type Meta,
  type PlaceResult,
  type PlaceSummary,
  type WeatherNow,
} from './api'

const MINUTE = 60_000

export function useDistricts() {
  return useQuery({
    queryKey: ['districts'],
    queryFn: () => apiGet<Meta & { districts: District[] }>('/places/districts'),
    staleTime: 60 * MINUTE,
    select: (data) => data.districts,
  })
}

export function usePlaceSummaries(ids: string[]) {
  return useQuery({
    queryKey: ['place-summary', ids],
    queryFn: () => apiGet<Meta & { places: PlaceSummary[] }>('/places/summary', { ids: ids.join(',') }),
    enabled: ids.length > 0,
    staleTime: 5 * MINUTE,
  })
}

export function usePlaceSearch(q: string) {
  const term = q.trim()
  return useQuery({
    queryKey: ['place-search', term.toLowerCase()],
    queryFn: () => apiGet<Meta & { results: PlaceResult[] }>('/places/search', { q: term }),
    enabled: term.length >= 2,
    staleTime: 60 * MINUTE,
  })
}

export function useAirNow(place: string) {
  return useQuery({
    queryKey: ['air-now', place],
    queryFn: () => apiGet<AirNow>(`/air/${place}/now`),
    staleTime: 5 * MINUTE,
    refetchInterval: 10 * MINUTE,
  })
}

export function useWeatherNow(place: string) {
  return useQuery({
    queryKey: ['weather-now', place],
    queryFn: () => apiGet<WeatherNow>(`/weather/${place}/now`),
    staleTime: 5 * MINUTE,
    refetchInterval: 10 * MINUTE,
  })
}

const air = <T,>(place: string, part: string) => () => apiGet<T>(`/air/${place}/${part}`)

export function useAirHourly(place: string) {
  return useQuery({
    queryKey: ['air-hourly', place],
    queryFn: air<Meta & { hours: AirHour[] }>(place, 'hourly'),
    staleTime: 5 * MINUTE,
  })
}

export function useAirDaily(place: string, enabled = true) {
  return useQuery({
    queryKey: ['air-daily', place],
    queryFn: air<Meta & { days: AirDay[]; note: string }>(place, 'daily'),
    staleTime: 15 * MINUTE,
    enabled,
  })
}

export function useAirMonthly(place: string, enabled = true) {
  return useQuery({
    queryKey: ['air-monthly', place],
    queryFn: air<Meta & { months: AirMonth[] }>(place, 'monthly'),
    staleTime: 60 * MINUTE,
    enabled,
  })
}

export function useAirPollutants(place: string) {
  return useQuery({
    queryKey: ['air-pollutants', place],
    queryFn: air<Meta & { pollutants: PollutantValue[]; co2: Co2 | null }>(place, 'pollutants'),
    staleTime: 5 * MINUTE,
  })
}

export function useAirStations(place: string) {
  return useQuery({
    queryKey: ['air-stations', place],
    queryFn: air<Meta & { stations: StationPin[] }>(place, 'stations'),
    staleTime: 5 * MINUTE,
  })
}

export function useWind(place: string) {
  return useQuery({ queryKey: ['wind', place], queryFn: air<Wind>(place, 'wind'), staleTime: 5 * MINUTE })
}

export function useAdvice(place: string) {
  return useQuery({ queryKey: ['advice', place], queryFn: air<Advice>(place, 'advice'), staleTime: 5 * MINUTE })
}

export function useAirMap(bbox: string | null) {
  return useQuery({
    queryKey: ['air-map', bbox],
    queryFn: () => apiGet<Meta & { cells: MapCell[]; grid: number }>('/air/map', { bbox: bbox! }),
    enabled: !!bbox,
    staleTime: 30 * MINUTE,
  })
}

const wx = <T,>(place: string, part: string, params?: Record<string, string>) => () =>
  apiGet<T>(`/weather/${place}/${part}`, params)

export function useWeatherFull(place: string) {
  return useQuery({ queryKey: ['weather-now', place], queryFn: wx<WeatherNowFull>(place, 'now'), staleTime: 5 * MINUTE })
}

export function useWeatherHourly(place: string) {
  return useQuery({
    queryKey: ['weather-hourly', place],
    queryFn: wx<Meta & { hours: WeatherHour[]; note: string }>(place, 'hourly'),
    staleTime: 10 * MINUTE,
  })
}

export function useWeatherDaily(place: string, days = 11) {
  return useQuery({
    queryKey: ['weather-daily', place, days],
    queryFn: wx<Meta & { days: WeatherDay[] }>(place, 'daily', { days: String(days) }),
    staleTime: 30 * MINUTE,
  })
}

export function useSun(place: string) {
  return useQuery({ queryKey: ['sun', place], queryFn: wx<Meta & { days: SunDay[] }>(place, 'sun'), staleTime: 60 * MINUTE })
}

export function useUv(place: string) {
  return useQuery({ queryKey: ['uv', place], queryFn: wx<Uv>(place, 'uv'), staleTime: 10 * MINUTE })
}

export function useHeatSummary(place: string) {
  return useQuery({
    queryKey: ['heat', place],
    queryFn: () => apiGet<HeatSummary>(`/heat/${place}`),
    staleTime: 10 * MINUTE,
  })
}

/** Same request as useHeatSummary (shared cache), typed as the full report. */
export function useHeat(place: string) {
  return useQuery({
    queryKey: ['heat', place],
    queryFn: () => apiGet<HeatReport>(`/heat/${place}`),
    staleTime: 10 * MINUTE,
  })
}
