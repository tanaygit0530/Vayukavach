import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudMoon,
  CloudSun,
  Moon,
  Sun,
} from 'lucide-react'

/** Icon for a WMO weather code (Open-Meteo). Decorative: the condition text carries meaning. */
export function SkyIcon({
  code,
  className = 'h-5 w-5',
  night = false,
}: {
  code: number | null | undefined
  className?: string
  /** After sunset: clear and partly cloudy skies show the moon. */
  night?: boolean
}) {
  const props = { 'aria-hidden': true as const, className, strokeWidth: 1.8 }
  if (code === null || code === undefined) return <Cloud {...props} className={`${className} text-slate-400`} />
  if (code === 0)
    return night ? <Moon {...props} className={`${className} text-indigo-400`} /> : <Sun {...props} className={`${className} text-amber-500`} />
  if (code <= 2)
    return night ? <CloudMoon {...props} className={`${className} text-indigo-400`} /> : <CloudSun {...props} className={`${className} text-sky-500`} />
  if (code === 3) return <Cloud {...props} className={`${className} text-slate-400`} />
  if (code === 45 || code === 48) return <CloudFog {...props} className={`${className} text-slate-400`} />
  if (code >= 95) return <CloudLightning {...props} className={`${className} text-indigo-500`} />
  if ((code >= 71 && code <= 77) || code === 85 || code === 86)
    return <CloudSnow {...props} className={`${className} text-sky-400`} />
  if (code >= 51 && code <= 57) return <CloudDrizzle {...props} className={`${className} text-sky-500`} />
  return <CloudRain {...props} className={`${className} text-sky-600`} />
}
