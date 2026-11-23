export const IST_TZ = 'Asia/Kolkata'

export function formatIstTime(date: Date): string {
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: IST_TZ,
  }).format(date)
}

/** "Updated 3 h ago" / "Updated 25 min ago" / "Updated just now". */
export function updatedAgo(iso: string | null, now: Date = new Date()): string | null {
  if (!iso) return null
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000))
  if (minutes < 2) return 'Updated just now'
  if (minutes < 60) return `Updated ${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `Updated ${hours} h ago`
  return `Updated ${Math.round(hours / 24)} days ago`
}

export const POLLUTANT_NAMES: Record<string, string> = {
  pm25: 'PM2.5',
  pm10: 'PM10',
  no2: 'NO₂',
  so2: 'SO₂',
  co: 'CO',
  o3: 'O₃',
  nh3: 'NH₃',
}

export function round(value: number | null | undefined, digits = 0): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null
  return value.toFixed(digits)
}
