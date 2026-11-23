import { useQuery } from '@tanstack/react-query'

import {
  apiGet,
  type AirNow,
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
