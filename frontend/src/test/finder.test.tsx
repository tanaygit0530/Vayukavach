import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from '../components/shell/AppShell'
import { betterText, fmtMinutes, valueText } from '../lib/finder'
import { FinderPage } from '../pages/FinderPage'
import { mockApi } from './render'

const META = { source: 'test', updated_at: new Date().toISOString(), label: 'mixed', stale: false }

function finderBody(goal: string, mode: string) {
  if (goal === 'heat' && mode === 'nearby')
    return { ...META, goal, mode, radius_km: 10, origin: { name: 'Delhi', lat: 28.6, lon: 77.2, value: null },
      places: [], precautions: [], empty_reason: 'Park- and lake-level cooling needs satellite data.', note: 'n' } // prettier-ignore
  return {
    ...META, goal, mode, radius_km: 150, origin: { name: 'Delhi', lat: 28.6, lon: 77.2, value: 234 },
    places: [
      { id: 'town-kotputli', name: 'Kotputli', state: 'Rajasthan', lat: 27.7, lon: 76.2, kind: 'town',
        distance_km: 141.2, approx_minutes: 185, value: 56, unit: 'AQI', value_label: 'measured',
        value_source: 'CPCB station, latest hour', category: 'Satisfactory', category_key: 'satisfactory',
        forecast: [{ date: '2026-11-24', value: 87 }], forecast_label: 'estimated', better_by: 178, score: 70 },
    ],
    precautions: [{ for: 'Where you are now', text: 'Poor: May cause breathing discomfort.', source: 'CPCB' }],
    empty_reason: null, note: 'Ranked by 60% today + 40% outlook.',
  } // prettier-ignore
}

function renderFinder(path: string) {
  const base = mockApi()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input))
    if (url.pathname.endsWith('/finder'))
      return new Response(JSON.stringify(finderBody(url.searchParams.get('goal')!, url.searchParams.get('mode')!)))
    if (url.pathname.endsWith('/route'))
      return new Response(JSON.stringify({ ...META, distance_km: 167.8, duration_min: 130,
        geometry: [[28.6, 77.2], [27.7, 76.2]], maps_url: 'https://www.google.com/maps/dir/?api=1&x' })) // prettier-ignore
    return base(input)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="finder" element={<FinderPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Finder', () => {
  it('lists labelled places and shows the route with precautions and navigation', async () => {
    const user = userEvent.setup()
    renderFinder('/finder?place=delhi&goal=air&mode=daytrip')
    const item = await screen.findByRole('button', { name: /kotputli/i })
    expect(within(item).getByText('Measured')).toBeInTheDocument()
    expect(within(item).getByText('AQI 56')).toBeInTheDocument()
    await user.click(item)
    expect(await screen.findByText('167.8 km')).toBeInTheDocument()
    expect(screen.getByText('178 AQI points cleaner than here')).toBeInTheDocument()
    expect(screen.getByText(/Where you are now:/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /start navigation/i })).toHaveAttribute('href', expect.stringContaining('google.com/maps/dir'))
  })

  it('nearby heat shows the honest empty state', async () => {
    renderFinder('/finder?place=delhi&goal=heat&mode=nearby')
    expect(await screen.findByText(/satellite data/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /kotputli/i })).not.toBeInTheDocument()
  })

  it('mode cards are radios', async () => {
    const user = userEvent.setup()
    renderFinder('/finder?place=delhi&goal=air&mode=daytrip')
    const vacation = await screen.findByRole('radio', { name: /vacation/i })
    await user.click(vacation)
    expect(vacation).toHaveAttribute('aria-checked', 'true')
  })

  it('formatting helpers', () => {
    expect(fmtMinutes(45)).toBe('45 min')
    expect(fmtMinutes(130)).toBe('2 h 10 min')
    expect(fmtMinutes(2950)).toBe('2 days')
    expect(valueText('heat', { value: 29.84 })).toBe('29.8°C')
    expect(betterText('air', 178)).toBe('178 AQI points cleaner than here')
    expect(betterText('heat', -1)).toBeNull()
  })
})
