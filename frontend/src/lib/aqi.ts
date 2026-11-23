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
