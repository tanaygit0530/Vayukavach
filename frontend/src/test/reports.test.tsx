import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from '../components/shell/AppShell'
import { istDate } from '../lib/time'
import { ReportsPage } from '../pages/ReportsPage'
import { mockApi } from './render'

const station = (id: number, pct: number, pollutant = 'pm25') => ({
  station_id: id, name: `Station ${id}`, pollutant, expected: 24, received: Math.round((24 * pct) / 100),
  excluded: 0, pct, longest_gap_hours: 24 - Math.round((24 * pct) / 100),
}) // prettier-ignore

const REPORT = {
  source: 'CPCB/SPCB stations via OpenAQ', updated_at: new Date().toISOString(), label: 'measured', stale: false,
  district: 'delhi', date: '2026-11-23', completeness_pct: 91.6,
  gap_bias: { flagged: true, polluted_hours_missing_pct: 18, clean_hours_missing_pct: 4, difference_pp: 14 },
  silent_stations: [{ station_id: 4, name: 'R K Puram', from: '2026-11-23T14:30:00Z', to: '2026-11-23T17:30:00Z' }],
  city_silent_hours: [],
  readings_near_limit: [{ station_id: 9, name: 'Anand Vihar', hour: '2026-11-23T18:30:00Z', pollutant: 'pm10', value: 999, at_or_over_999: true }],
  stations: [station(13, 45.8), station(57, 58.3, 'pm10'), station(72, 95)],
  wording: 'This report describes data completeness only. It does not assign blame.',
} // prettier-ignore

function renderReports(path: string, body: unknown = REPORT) {
  const base = mockApi()
  const urls: URL[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input))
    if (url.pathname.includes('/reports/')) {
      urls.push(url)
      return new Response(JSON.stringify(body))
    }
    return base(input)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="reports" element={<ReportsPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return urls
}

describe('Data report', () => {
  it('shows completeness, silent stations, flagged hours and the low stations, with a CSV link', async () => {
    const user = userEvent.setup()
    const urls = renderReports('/reports?place=delhi&date=2026-11-23')
    expect(await screen.findByText('92%')).toBeInTheDocument()
    expect(urls[0].searchParams.get('date')).toBe('2026-11-23')
    expect(screen.getByText('Flagged: gaps clustered in polluted hours')).toBeInTheDocument()
    expect(screen.getByText('R K Puram')).toBeInTheDocument()
    expect(screen.getByText('20:00–23:00')).toBeInTheDocument() // IST
    expect(screen.getByText(/Anand Vihar: PM10 999/)).toBeInTheDocument()

    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(3) // header + 2 rows below 75%
    await user.click(screen.getByRole('button', { name: 'Show all' }))
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(4)

    const csv = screen.getByRole('link', { name: /Download CSV/ })
    expect(csv.getAttribute('href')).toContain('/reports/delhi/gaps?date=2026-11-23&format=csv')
    expect(screen.getByText(/does not assign blame/)).toBeInTheDocument()
  })

  it('defaults to yesterday and explains an empty day', async () => {
    const urls = renderReports('/reports?place=delhi', { ...REPORT, stations: [], silent_stations: [] })
    expect(await screen.findByText(/No station data for/)).toBeInTheDocument()
    expect(urls[0].searchParams.get('date')).toBe(istDate(-1))
  })

  it('computes IST dates across midnight', () => {
    // 20:00 UTC on 23 Nov is 01:30 IST on 24 Nov
    expect(istDate(0, new Date('2026-11-23T20:00:00Z'))).toBe('2026-11-24')
    expect(istDate(-1, new Date('2026-11-23T20:00:00Z'))).toBe('2026-11-23')
  })
})
