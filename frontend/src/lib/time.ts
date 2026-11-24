/** IST calendar date, offset by `days`. */
export function istDate(days = 0, now = new Date()): string {
  const d = new Date(now.getTime() + days * 86_400_000)
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(d)
}
