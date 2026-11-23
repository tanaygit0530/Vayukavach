/** CPCB category colours (token names match tailwind `aqi.*` and CSS variables). */
export const AQI_KEYS = ['good', 'satisfactory', 'moderate', 'poor', 'verypoor', 'severe'] as const
export type AqiKey = (typeof AQI_KEYS)[number]

export const AQI_LABELS: Record<AqiKey, string> = {
  good: 'Good',
  satisfactory: 'Satisfactory',
  moderate: 'Moderate',
  poor: 'Poor',
  verypoor: 'Very poor',
  severe: 'Severe',
}

export function aqiVar(key: string | null | undefined): string {
  return key && (AQI_KEYS as readonly string[]).includes(key) ? `var(--aqi-${key})` : '#b8c1c9'
}

const BANDS: [number, AqiKey][] = [
  [50, 'good'],
  [100, 'satisfactory'],
  [200, 'moderate'],
  [300, 'poor'],
  [400, 'verypoor'],
  [500, 'severe'],
]

export function aqiKey(aqi: number | null | undefined): AqiKey | null {
  if (aqi === null || aqi === undefined) return null
  const v = Math.round(aqi)
  return (BANDS.find(([upper]) => v <= upper) ?? BANDS[BANDS.length - 1])[1]
}

/** Light category colours need a darker outline to stand out on white (contrast < 3:1). */
export const LIGHT_KEYS = new Set<AqiKey>(['good', 'satisfactory', 'moderate', 'poor'])
