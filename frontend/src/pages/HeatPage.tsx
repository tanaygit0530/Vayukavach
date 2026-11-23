import { useEffect } from 'react'

import {
  HeatCard,
  HeatForecast,
  HeatHero,
  HeatStress,
  HourlyStrip,
  SafeWorkArc,
  UvCard,
  WhatToDo,
} from '../components/heat/HeatParts'
import { StaleBadge } from '../components/ui/Badges'
import { HEAT_THEME, isLevel } from '../lib/heat'
import { useDistricts, useHeat } from '../lib/queries'
import { useShell } from '../lib/shell'

/** Paint the page background for the current level (CSS variables, animated). */
function useHeatTheme(level: string | null | undefined) {
  useEffect(() => {
    const theme = HEAT_THEME[isLevel(level) ? level : 'normal']
    const root = document.documentElement.style
    root.setProperty('--heat-bg-centre', theme.centre)
    root.setProperty('--heat-bg-edge', theme.edge)
    root.setProperty('--heat-bg-glow', theme.glow)
    document.documentElement.dataset.heatLevel = isLevel(level) ? level : 'normal'
    return () => {
      delete document.documentElement.dataset.heatLevel
    }
  }, [level])
}

export function HeatPage() {
  const { place } = useShell()
  const districts = useDistricts()
  const district = districts.data?.find((d) => d.id === place)
  const heat = useHeat(place)
  const d = heat.data
  useHeatTheme(d?.level)

  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">Heat risk in {district?.name ?? place}</h1>
      {d && d.stale && (
        <div className="self-center"><StaleBadge updatedAt={d.updated_at} stale /></div>
      )}
      <HeatHero data={d} district={district ? `${district.name}, ${district.state}` : place} loading={heat.isLoading} />
      {heat.isError && (
        <HeatCard title="Heat data unavailable"><p className="text-[14px]">Could not load heat data. Try again shortly.</p></HeatCard>
      )}
      {d && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SafeWorkArc data={d} />
          <HourlyStrip hours={d.hourly} />
          <HeatStress data={d} />
          <HeatForecast days={d.daily} />
          <div className="flex flex-col gap-4">
            <UvCard place={place} />
            <WhatToDo data={d} place={place} />
          </div>
        </div>
      )}
    </div>
  )
}
