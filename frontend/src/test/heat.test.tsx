import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from '../components/shell/AppShell'
import {
  arcSegments,
  CARD_DARKEN,
  contrast,
  darken,
  HEAT_LEVELS,
  HEAT_THEME,
  windowsText,
} from '../lib/heat'
import { HeatPage } from '../pages/HeatPage'
import { mockApi } from './render'

describe('heat theme accessibility', () => {
  it.each(HEAT_LEVELS)('%s: white text >= 4.5:1 on the gradient centre and on cards', (level) => {
    const t = HEAT_THEME[level]
    expect(contrast('#ffffff', t.centre)).toBeGreaterThanOrEqual(4.5)
    for (const bg of [t.centre, t.edge, t.glow]) {
      expect(contrast('#ffffff', darken(bg, CARD_DARKEN))).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('the spec centre colours alone would fail (why we darken)', () => {
    expect(contrast('#ffffff', '#38BDF8')).toBeLessThan(4.5)
    expect(contrast('#ffffff', '#FCD34D')).toBeLessThan(4.5)
  })
})

describe('safe work hours', () => {
  const hourly = Array.from({ length: 24 }, (_, h) => ({
    local_hour: h,
    level: h >= 11 && h <= 15 ? 'danger' : h === 10 || h === 16 ? 'caution' : 'normal',
  }))

  it('arc has one segment per work hour, safe only when Normal', () => {
    const segs = arcSegments(hourly)
    expect(segs).toHaveLength(13)
    expect(segs.filter((s) => s.safe).map((s) => s.hour)).toEqual([6, 7, 8, 9, 17, 18])
    expect(segs.find((s) => s.hour === 12)?.level).toBe('danger')
  })

  it('window text', () => {
    expect(windowsText([{ from_hour: 6, to_hour: 10 }, { from_hour: 17, to_hour: 19 }])).toBe('6 AM–10 AM, 5 PM–7 PM')
    expect(windowsText([])).toMatch(/No safe window/)
  })
})

function heatResponse(level: string) {
  return {
    source: 'test', updated_at: new Date().toISOString(), label: 'estimated', stale: false, district: 'delhi',
    hour: null, temperature: 38, humidity: 55, feels_like: 45, heat_index: 47, wet_bulb: 29, level,
    level_name: level[0].toUpperCase() + level.slice(1), instruction: 'Instruction text', worst_level_today: level,
    safe_work_windows: [{ from_hour: 6, to_hour: 9 }],
    hourly: [{ hour: '2099-01-01T00:00:00Z', local_hour: 6, temperature: 30, feels_like: 31, heat_index: 31, wet_bulb: 24, level: 'normal' }],
    daily: [], tips: ['Drink water often.'], tips_source: 'NDMA', thresholds_status: 'draft',
  } // prettier-ignore
}

function renderHeat() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/heat?place=delhi']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="heat" element={<HeatPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Heat page', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.documentElement.removeAttribute('style')
  })

  it.each(['normal', 'danger', 'extreme'])('paints the %s gradient and shows the level', async (level) => {
    const base = mockApi()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (new URL(String(input)).pathname.endsWith('/heat/delhi')) {
        return new Response(JSON.stringify(heatResponse(level)), { status: 200 })
      }
      return base(input)
    }))
    renderHeat()
    expect(await screen.findByLabelText('Feels like 45 degrees Celsius')).toBeInTheDocument()
    await waitFor(() =>
      expect(document.documentElement.style.getPropertyValue('--heat-bg-centre')).toBe(
        HEAT_THEME[level as keyof typeof HEAT_THEME].centre,
      ),
    )
    expect(document.documentElement.dataset.heatLevel).toBe(level)
    expect(screen.getByRole('link', { name: /find cooler places/i })).toHaveAttribute('href', '/finder?place=delhi&goal=heat')
    expect(screen.getByText('6 AM–9 AM')).toBeInTheDocument()
  })
})
