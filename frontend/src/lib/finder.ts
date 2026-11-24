import type { FinderPlace, Goal } from './api'

export function fmtMinutes(min: number): string {
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  if (h >= 24) return `${Math.round(min / 60 / 24 * 10) / 10} days`
  return m ? `${h} h ${m} min` : `${h} h`
}

export function valueText(goal: Goal, p: Pick<FinderPlace, 'value'>): string {
  return goal === 'air' ? `AQI ${Math.round(p.value)}` : `${p.value.toFixed(1)}°C`
}

export function betterText(goal: Goal, by: number | null): string | null {
  if (by === null || by <= 0) return null
  return goal === 'air' ? `${Math.round(by)} AQI points cleaner than here` : `${by.toFixed(1)}°C cooler than here`
}

export const MODES = [
  { id: 'nearby', title: 'Nearby', detail: 'within 10 km' },
  { id: 'daytrip', title: 'Day trip', detail: 'within 150 km' },
  { id: 'vacation', title: 'Vacation', detail: 'anywhere in India' },
] as const
