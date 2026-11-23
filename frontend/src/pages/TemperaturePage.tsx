import { Download, Thermometer } from 'lucide-react'
import { useState } from 'react'

import {
  ConditionGrid,
  FeelsLikeCard,
  ForecastList,
  MyLocationCard,
  SunArc,
  TempTrend,
  UvGauge,
} from '../components/temperature/Cards'
import { useDistricts, useWeatherDaily, useWeatherFull, useWeatherHourly } from '../lib/queries'
import { useShell } from '../lib/shell'
import { weatherCsv } from '../lib/weather'

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function TemperaturePage() {
  const { place } = useShell()
  const districts = useDistricts()
  const district = districts.data?.find((d) => d.id === place)
  const now = useWeatherFull(place)
  const hourly = useWeatherHourly(place)
  const daily = useWeatherDaily(place, 11)
  const [exported, setExported] = useState<string | null>(null)
  const ready = !!hourly.data && !!daily.data

  const exportCsv = () => {
    if (!hourly.data || !daily.data) return
    const stamp = new Date().toISOString().slice(0, 10)
    const name = `vayukavach-weather-${place}-${stamp}.csv`
    download(name, weatherCsv(place, hourly.data.hours, daily.data.days))
    setExported(name)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[15px] font-medium">
          <Thermometer aria-hidden className="h-4 w-4" /> Temperature
        </h1>
        <div className="flex items-center gap-3">
          <p className="hidden text-[12px] text-ink-muted sm:block">All values: Open-Meteo model (Estimated)</p>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!ready}
            className="focus-ring inline-flex min-h-touch items-center gap-2 rounded-full bg-ink px-5 text-[14px] font-medium text-white disabled:opacity-50"
          >
            <Download aria-hidden className="h-4 w-4" /> Export CSV
          </button>
        </div>
      </div>
      <p role="status" className="sr-only">{exported ? `Downloaded ${exported}` : ''}</p>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="flex flex-col gap-4 xl:row-span-2">
          <MyLocationCard
            place={place}
            name={district?.name ?? place}
            state={district?.state ?? ''}
            now={now.data}
            loading={now.isLoading}
          />
          <FeelsLikeCard place={place} now={now.data} loading={now.isLoading} />
        </div>
        <div className="md:col-span-2 xl:col-span-2">
          <TempTrend hours={hourly.data?.hours} loading={hourly.isLoading} />
        </div>
        <div className="xl:row-span-2">
          <ConditionGrid now={now.data} today={daily.data?.days[0]} loading={now.isLoading || daily.isLoading} />
        </div>
        <ForecastList days={daily.data?.days} loading={daily.isLoading} />
        <div className="flex flex-col gap-4">
          <SunArc place={place} />
          <UvGauge place={place} />
        </div>
      </div>
    </div>
  )
}
