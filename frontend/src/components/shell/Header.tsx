import { Cloud, CloudRain, CloudSun, Sun } from 'lucide-react'
import { forwardRef, useEffect, useState } from 'react'
import { useLocation } from 'react-router'

import { formatIstTime } from '../../lib/format'
import { useWeatherNow } from '../../lib/queries'
import { StaleBadge } from '../ui/Badges'
import { LocationButton } from './LocationButton'

function WeatherIcon({ code }: { code: number | null | undefined }) {
  const cls = 'h-4 w-4 text-sky-500'
  if (code === null || code === undefined) return <Cloud aria-hidden className={cls} />
  if (code === 0) return <Sun aria-hidden className="h-4 w-4 text-amber-500" />
  if (code <= 2) return <CloudSun aria-hidden className={cls} />
  if (code >= 51) return <CloudRain aria-hidden className={cls} />
  return <Cloud aria-hidden className={cls} />
}

function useClock(intervalMs = 30_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

interface HeaderProps {
  place: string
  drawerOpen: boolean
  onOpenPlaces: () => void
}

/** Location button on the left; time, weather and data label on the right. */
export const Header = forwardRef<HTMLButtonElement, HeaderProps>(function Header(
  { place, drawerOpen, onOpenPlaces },
  ref,
) {
  const now = useClock()
  const weather = useWeatherNow(place)
  // The Temperature tab shows the temperature in its own card: each number once per screen.
  const { pathname } = useLocation()
  const temp = pathname === '/temperature' ? null : weather.data?.temperature
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <LocationButton ref={ref} place={place} open={drawerOpen} onClick={onOpenPlaces} />
      <div className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[14px]">
        <WeatherIcon code={weather.data?.weather_code} />
        {temp !== null && temp !== undefined && (
          <span className="font-medium">{Math.round(temp)}°C</span>
        )}
        <time dateTime={now.toISOString()} className="text-ink">
          {formatIstTime(now)} IST
        </time>
        {weather.data && (
          <span className="hidden text-[12px] text-ink-muted sm:inline">· Open-Meteo, Estimated</span>
        )}
        {weather.data && (
          <StaleBadge updatedAt={weather.data.updated_at} stale={weather.data.stale} />
        )}
      </div>
    </header>
  )
})
