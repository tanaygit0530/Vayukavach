import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ForecastList, TempTrend } from '../components/temperature/Cards'
import type { WeatherDay, WeatherHour } from '../lib/api'
import { fmtDuration, sunFraction, trendPoints, uvAngle, weatherCsv } from '../lib/weather'

// 2026-11-23 00:00 IST = 2026-11-22 18:30 UTC
const DAY0 = Date.UTC(2026, 10, 22, 18, 30)
const hour = (h: number, temp: number | null, forecast = false): WeatherHour => ({
  hour: new Date(DAY0 + h * 3600_000).toISOString(), temperature: temp, apparent_temperature: temp,
  humidity: 50, dew_point: 10, wind_speed: 5, wind_gusts: 9, wind_direction: 270, pressure: 1012,
  cloud_cover: 10, precipitation: 0, precipitation_probability: 5, visibility: 9000, uv_index: 0,
  weather_code: 0, boundary_layer_height: 300, condition: 'Clear, sky', is_forecast: forecast,
}) // prettier-ignore
const NOW = new Date(DAY0 + 14.5 * 3600_000) // 14:30 IST

describe('temperature helpers', () => {
  const hours = Array.from({ length: 24 }, (_, h) => hour(h, 10 + h, h > 14))

  it('trend: 13 points 7 AM-7 PM, current hour marked', () => {
    const pts = trendPoints(hours, NOW)
    expect(pts).toHaveLength(13)
    expect(pts[0]).toMatchObject({ hour: 7, temp: 17 })
    expect(pts.find((p) => p.isNow)?.hour).toBe(14)
    expect(pts.filter((p) => p.isForecast).map((p) => p.hour)).toEqual([15, 16, 17, 18, 19])
  })

  it('sun position and night', () => {
    const rise = new Date(DAY0 + 6 * 3600_000).toISOString()
    const set = new Date(DAY0 + 18 * 3600_000).toISOString()
    expect(sunFraction(rise, set, new Date(DAY0 + 12 * 3600_000))).toBeCloseTo(0.5)
    expect(sunFraction(rise, set, new Date(DAY0 + 20 * 3600_000))).toBeNull()
    expect(fmtDuration(38_100)).toBe('10h 35m')
  })

  it('UV gauge angle is clamped', () => {
    expect(uvAngle(0)).toBe(-90)
    expect(uvAngle(6)).toBe(0)
    expect(uvAngle(20)).toBe(90)
  })

  it('CSV: one table, missing values empty (never 0), commas escaped', () => {
    const day: WeatherDay = { date: '2026-11-23', temperature_min: 12, temperature_max: null,
      apparent_temperature_max: 20, weather_code: 0, condition: 'Clear', precipitation_sum: null,
      precipitation_probability_max: 0, uv_index_max: 4, is_forecast: false } // prettier-ignore
    const csv = weatherCsv('delhi', [hour(0, null)], [day])
    const [head, h, d] = csv.trim().split('\n')
    expect(head.split(',')).toContain('temperature_c')
    expect(h.startsWith('hourly,delhi,')).toBe(true)
    expect(h.split(',')[3]).toBe('') // missing temperature stays empty
    expect(h).toContain('"Clear, sky"')
    expect(d.startsWith('daily,delhi,2026-11-23')).toBe(true)
    expect(d.split(',')[15]).toBe('') // temperature_max missing (column 15)
  })
})

describe('temperature cards', () => {
  it('trend shows "Now" instead of repeating the current temperature', () => {
    const hours = Array.from({ length: 24 }, (_, h) => hour(h, 10 + h, h > 14))
    render(<TempTrend hours={hours} loading={false} now={NOW} />)
    const list = screen.getByRole('list', { name: 'Hourly temperature' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(13)
    expect(within(list).getByText('Now')).toBeInTheDocument()
    expect(within(list).queryByText('24°')).not.toBeInTheDocument() // 14:00 value hidden behind "Now"
  })

  it('forecast list starts tomorrow (today is on the location card)', () => {
    const days: WeatherDay[] = Array.from({ length: 11 }, (_, i) => ({
      date: `2026-11-${String(23 + i).padStart(2, '0')}`.replace('2026-11-31', '2026-12-01').replace('2026-11-32', '2026-12-02').replace('2026-11-33', '2026-12-03'),
      temperature_min: 10 + i, temperature_max: 20 + i, apparent_temperature_max: 20, weather_code: 0,
      condition: 'Clear sky', precipitation_sum: 0, precipitation_probability_max: 0, uv_index_max: 4, is_forecast: i > 0,
    })) // prettier-ignore
    render(<ForecastList days={days} loading={false} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(10)
    expect(items[0]).toHaveTextContent('Tue 24')
    expect(screen.queryByText('Mon 23')).not.toBeInTheDocument()
  })
})
