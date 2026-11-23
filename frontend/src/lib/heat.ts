/** Heat-tab theme and helpers. Level thresholds live in the backend (draft, see app/analysis/heat.py). */

export const HEAT_LEVELS = ['normal', 'caution', 'danger', 'extreme'] as const
export type HeatLevel = (typeof HEAT_LEVELS)[number]

export const LEVEL_NAMES: Record<HeatLevel, string> = {
  normal: 'Normal',
  caution: 'Caution',
  danger: 'Danger',
  extreme: 'Extreme',
}

/**
 * Background per level: centre -> edge -> outer glow.
 * The spec's centre colours (#38BDF8, #FCD34D) give white text only 2.1:1 and 1.4:1, so the
 * centre is darkened (spec: "darken the gradient centre if needed"); the spec's light colour
 * stays as the outer glow, away from text. Cards add 38% black glass. Contrast is unit-tested.
 */
export const HEAT_THEME: Record<HeatLevel, { centre: string; edge: string; glow: string; accent: string }> = {
  normal: { centre: '#0369A1', edge: '#1E3A8A', glow: '#38BDF8', accent: '#7DD3FC' },
  caution: { centre: '#B45309', edge: '#D97706', glow: '#F59E0B', accent: '#FCD34D' },
  danger: { centre: '#B91C1C', edge: '#EA580C', glow: '#F97316', accent: '#FDBA74' },
  extreme: { centre: '#991B1B', edge: '#3B0A0A', glow: '#7F1D1D', accent: '#FCA5A5' },
}

export const CARD_DARKEN = 0.38

export const isLevel = (v: string | null | undefined): v is HeatLevel =>
  !!v && (HEAT_LEVELS as readonly string[]).includes(v)

// ---------------------------------------------------------------- contrast (WCAG 2.x)

const channel = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
export function luminance(hex: string): number {
  const [r, g, b] = (hex.replace('#', '').match(/\w\w/g) ?? []).map((h) => channel(parseInt(h, 16) / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}
export function darken(hex: string, amount: number): string {
  return (
    '#' +
    (hex.replace('#', '').match(/\w\w/g) ?? [])
      .map((h) => Math.round(parseInt(h, 16) * (1 - amount)).toString(16).padStart(2, '0'))
      .join('')
  )
}

// ---------------------------------------------------------------- work-day arc

export const WORK_START = 6
export const WORK_END = 19

export interface ArcSegment {
  hour: number
  level: HeatLevel | null
  safe: boolean
}

export function arcSegments(hourly: { local_hour: number; level: string | null }[]): ArcSegment[] {
  const byHour = new Map(hourly.map((h) => [h.local_hour, h.level]))
  return Array.from({ length: WORK_END - WORK_START }, (_, i) => {
    const hour = WORK_START + i
    const level = byHour.get(hour) ?? null
    return { hour, level: isLevel(level) ? level : null, safe: level === 'normal' }
  })
}

export const clock = (h: number) => `${h % 12 === 0 ? 12 : h % 12} ${h < 12 || h === 24 ? 'AM' : 'PM'}`

export function windowsText(windows: { from_hour: number; to_hour: number }[]): string {
  if (!windows.length) return 'No safe window today: avoid heavy outdoor work'
  return windows.map((w) => `${clock(w.from_hour)}–${clock(w.to_hour)}`).join(', ')
}
