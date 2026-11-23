import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'
import { vi } from 'vitest'

import App from '../App'

export const DISTRICTS = [
  { id: 'delhi', name: 'Delhi', state: 'Delhi', lat: 28.6, lon: 77.2 },
  { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', lat: 19.07, lon: 72.87 },
  { id: 'shimla', name: 'Shimla', state: 'Himachal Pradesh', lat: 31.1, lon: 77.17 },
]
const META = { source: 'test', updated_at: '2026-11-23T18:00:00+05:30', label: null, stale: false }

export function mockApi() {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input))
    const path = url.pathname.replace('/api/v1', '')
    let body: unknown = { detail: 'not found' }
    let status = 200
    if (path === '/places/districts') body = { ...META, districts: DISTRICTS }
    else if (path === '/places/summary')
      body = {
        ...META,
        places: DISTRICTS.map((d) => ({
          ...d, aqi: d.id === 'shimla' ? 120 : 250, category: 'Poor', category_key: 'poor',
          aqi_label: d.id === 'shimla' ? 'estimated' : 'measured', aqi_hour: null,
          temperature: 20, today_high: 25, today_low: 12, condition: 'Clear sky',
        })),
      } // prettier-ignore
    else if (path === '/places/search')
      body = {
        ...META,
        results: [
          { name: 'Navi Mumbai', state: 'Maharashtra', district: 'Thane', lat: 19.03, lon: 73.02,
            population: 1, covered_district: 'mumbai', distance_km: 16 },
          { name: 'Leh', state: 'Ladakh', district: 'Leh', lat: 34.1, lon: 77.5, population: 1,
            covered_district: null, distance_km: 340 },
        ],
      } // prettier-ignore
    else if (/^\/air\/[^/]+\/now$/.test(path))
      body = {
        ...META, label: 'measured', district: path.split('/')[2], aqi: 249, category: 'Poor',
        category_key: 'poor', main_pollutant: 'pm25', aqi_kind: 'official', hour: null,
        stations_reporting: 80, visibility_m: 3500, completeness_pct: 92.4, shadow_aqi: 251,
        shadow_aqi_low: 248, shadow_aqi_high: 256,
      } // prettier-ignore
    else if (/^\/weather\/[^/]+\/now$/.test(path))
      body = { ...META, label: 'estimated', district: 'delhi', temperature: 19.6, weather_code: 0 }
    else status = 404
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname + location.search}</output>
}

export function renderApp(path = '/air') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
