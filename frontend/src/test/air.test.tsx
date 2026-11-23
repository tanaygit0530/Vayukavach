import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AqiChart } from '../components/air/AqiChart'
import { PollutantBars } from '../components/air/PollutantBars'
import { WindCompass } from '../components/air/WindCompass'
import type { AirHour } from '../lib/api'
import { dailyColumns, hourlyColumns, monthlyColumns } from '../lib/aqiColumns'

const META = { source: 'test', updated_at: '2026-11-23T18:00:00+05:30', label: 'mixed', stale: false }

function hour(i: number, over: Partial<AirHour> = {}): AirHour {
  return {
    hour: new Date(Date.UTC(2026, 10, 22, 18, 30) + i * 3600_000).toISOString(),
    official_aqi: null, shadow_aqi: null, shadow_aqi_low: null, shadow_aqi_high: null,
    estimated_aqi: null, forecast_aqi: null, is_forecast: false, official_missing: true, ...over,
  } // prettier-ignore
}

describe('AQI chart columns', () => {
  it('hourly: official, shadow where missing, model, forecast, none', () => {
    const hours = [
      hour(0, { official_aqi: 310, official_missing: false, shadow_aqi: 305 }),
      hour(1, { shadow_aqi: 320, shadow_aqi_low: 300, shadow_aqi_high: 340 }),
      hour(2, { estimated_aqi: 150 }),
      hour(3),
      hour(4, { is_forecast: true, forecast_aqi: 200, official_missing: false }),
    ]
    const now = new Date(Date.UTC(2026, 10, 22, 22, 45)) // inside hour 4
    const cols = hourlyColumns(hours, now)
    expect(cols.map((c) => c.kind)).toEqual(['measured', 'shadow', 'estimated', 'none', 'forecast'])
    expect(cols[1].tooltip.join(' ')).toContain('Official reading missing')
    expect(cols[1].tooltip.join(' ')).toContain('(300–340)')
    expect(cols[3].value).toBeNull() // never a zero bar for missing data
    expect(cols[4].isNow).toBe(true)
    expect(cols[0].tooltip[1]).toContain('Very poor')
  })

  it('10 days: outlook days are placeholders', () => {
    const cols = dailyColumns([
      { date: '2026-11-23', low: 200, high: 270, is_outlook: false, available: true, label: 'estimated' },
      { date: '2026-11-28', low: null, high: null, is_outlook: true, available: false, label: 'estimated' },
    ])
    expect(cols[0]).toMatchObject({ low: 200, value: 270, kind: 'forecast' })
    expect(cols[1]).toMatchObject({ value: null, kind: 'outlook' })
    expect(cols[1].tooltip[1]).toBe('Outlook not available yet')
  })

  it('monthly: current month outlined, empty months stay empty', () => {
    const cols = monthlyColumns([
      { month: '2026-10', avg_aqi: null, days: 0, is_current: false },
      { month: '2026-11', avg_aqi: 248, days: 23, is_current: true },
    ])
    expect(cols[0]).toMatchObject({ value: null, kind: 'none' })
    expect(cols[1]).toMatchObject({ value: 248, outlined: true })
  })
})

function withQuery(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

function stubFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input)).pathname.replace('/api/v1', '')
      const body = routes[path]
      return new Response(JSON.stringify(body ?? { detail: 'x' }), { status: body ? 200 : 404 })
    }),
  )
}

describe('Air cards', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('pollutants: no reading is never shown as zero; CO2 is context only', async () => {
    stubFetch({
      '/air/delhi/pollutants': {
        ...META,
        pollutants: [
          { pollutant: 'pm25', value: 131, unit: 'ug/m3', sub_index: 270, label: 'measured', stations: 49 },
          { pollutant: 'nh3', value: null, unit: 'ug/m3', sub_index: null, label: null, stations: 0 },
          { pollutant: 'o3', value: 137, unit: 'ug/m3', sub_index: 154, label: 'estimated', stations: 0 },
        ],
        co2: { value: 469, unit: 'ppm', hour: '2026-11-23T18:00:00+05:30', label: 'estimated', note: 'Context only: CO2 is not part of India\'s AQI.' },
      },
    })
    withQuery(<PollutantBars place="delhi" />)
    expect(await screen.findByText(/Sub-index 270 · Poor · 49 stations/)).toBeInTheDocument()
    expect(screen.getByText('No reading')).toBeInTheDocument()
    expect(screen.getByText('Estimated')).toBeInTheDocument()
    expect(screen.getByText(/not part of India's AQI/)).toBeInTheDocument()
  })

  it('wind: speed, direction and dispersion note', async () => {
    stubFetch({
      '/air/delhi/wind': { ...META, label: 'estimated', speed_kmh: 3.2, gusts_kmh: 8, direction_deg: 292,
        direction_compass: 'WNW', boundary_layer_m: 120,
        note: 'Calm air and a low mixing layer are trapping pollution near the ground.' },
    }) // prettier-ignore
    withQuery(<WindCompass place="delhi" />)
    expect(await screen.findByText('3.2')).toBeInTheDocument()
    expect(screen.getByText(/From WNW/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Wind from WNW' })).toBeInTheDocument()
    expect(screen.getByText(/trapping pollution/)).toBeInTheDocument()
  })

  it('chart: tabs switch views and a table view exists', async () => {
    const user = userEvent.setup()
    stubFetch({
      '/air/delhi/hourly': { ...META, hours: [hour(0, { official_aqi: 250, official_missing: false })] },
      '/air/delhi/daily': { ...META, note: '', days: [
        { date: '2026-11-23', low: 200, high: 270, is_outlook: false, available: true, label: 'estimated' }] },
      '/air/delhi/monthly': { ...META, months: [{ month: '2026-11', avg_aqi: 248, days: 23, is_current: true }] },
    }) // prettier-ignore
    withQuery(<AqiChart place="delhi" />)
    expect(await screen.findByRole('img', { name: 'AQI chart' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show as table' }))
    const table = screen.getByRole('table')
    expect(within(table).getByText(/Official AQI 250 \(Poor\)/)).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '10 days' }))
    expect(await screen.findByText(/AQI 200–270/)).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Monthly' }))
    expect(await screen.findByText(/Average AQI 248/)).toBeInTheDocument()
  })
})
