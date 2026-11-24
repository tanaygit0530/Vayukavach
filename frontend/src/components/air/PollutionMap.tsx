import clsx from 'clsx'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Crosshair, Layers, Minus, Plus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { District, MapCell, StationPin } from '../../lib/api'
import { AQI_KEYS, AQI_LABELS, aqiVar } from '../../lib/aqi'
import { useAirMap, useAirStations } from '../../lib/queries'

const ZOOM = 11

function pinHtml(p: StationPin): string {
  const bg = p.status === 'silent' ? '#c7ced5' : aqiVar(p.category_key)
  const ring =
    p.status === 'measured'
      ? 'border:3px solid #fff;outline:2px solid #17212b'
      : p.status === 'estimated'
        ? 'border:3px solid #fff;outline:2px dashed #17212b'
        : 'border:3px solid #fff;outline:2px solid #8a96a1'
  const text = p.status === 'silent' ? '!' : String(p.aqi ?? '')
  const dark = p.category_key && ['poor', 'verypoor', 'severe'].includes(p.category_key) && p.status !== 'silent'
  return `<div class="vk-pin" style="background:${bg};${ring};color:${dark ? '#fff' : '#17212b'}">${text}</div>`
}

function pinLabel(p: StationPin): string {
  if (p.status === 'silent') return `${p.name}: not reporting`
  const kind = p.status === 'estimated' ? 'Estimated from nearby stations' : 'Measured'
  return `${p.name}: AQI ${p.aqi} (${p.category}) · ${kind}`
}

const userIcon = L.divIcon({
  className: '',
  html: '<div class="vk-user-pin"><span></span></div>',
  iconSize: [44, 44],
  iconAnchor: [22, 22],
})

/** Fixed box around the district: the same request for every viewer, so the server's
 * 1-hour cache is shared (Open-Meteo counts each grid point against a daily limit). */
function districtBbox(d: District): string {
  const f = (v: number) => v.toFixed(2)
  return [f(d.lon - 0.35), f(d.lat - 0.3), f(d.lon + 0.35), f(d.lat + 0.3)].join(',')
}

interface Props {
  place: string
  district: District | undefined
  className?: string
}

export function PollutionMap({ place, district, className }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const zones = useRef<L.LayerGroup | null>(null)
  const pins = useRef<L.LayerGroup | null>(null)
  const user = useRef<L.Marker | null>(null)
  const [showZones, setShowZones] = useState(true)
  const bbox = district ? districtBbox(district) : null
  const stations = useAirStations(place)
  const grid = useAirMap(bbox)

  // create the map once
  useEffect(() => {
    if (!el.current || map.current) return
    const m = L.map(el.current, {
      zoomControl: false,
      attributionControl: true,
      center: [22.5, 79],
      zoom: 5,
    })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      className: 'vk-tiles',
      attribution: '© OpenStreetMap contributors',
    }).addTo(m)
    m.attributionControl.setPrefix(false)
    m.attributionControl.addAttribution('PM2.5 zones: CAMS via Open-Meteo')
    m.createPane('zones').style.zIndex = '350'
    zones.current = L.layerGroup().addTo(m)
    pins.current = L.layerGroup().addTo(m)
    map.current = m
    return () => {
      m.remove()
      map.current = null
    }
  }, [])

  // centre on the district
  useEffect(() => {
    const m = map.current
    if (!m || !district) return
    m.setView([district.lat, district.lon], ZOOM, { animate: false })
    user.current?.remove()
    user.current = L.marker([district.lat, district.lon], {
      icon: userIcon,
      keyboard: false,
      title: `${district.name} (city centre)`,
      alt: `${district.name} city centre`,
      zIndexOffset: 1000,
    }).addTo(m)
  }, [district])

  // PM2.5 zones: one soft circle per grid cell, blurred by the pane's CSS filter
  useEffect(() => {
    const group = zones.current
    if (!group) return
    group.clearLayers()
    if (!showZones || !grid.data) return
    const cells: MapCell[] = grid.data.cells.filter((c) => c.pm25_sub_index !== null)
    if (cells.length < 2) return
    const lats = [...new Set(cells.map((c) => c.lat))].sort((a, b) => a - b)
    const spacingKm = lats.length > 1 ? (lats[1] - lats[0]) * 111 : 5
    for (const c of cells) {
      L.circle([c.lat, c.lon], {
        pane: 'zones',
        radius: spacingKm * 1000 * 0.85,
        stroke: false,
        fillColor: aqiVar(c.category_key),
        fillOpacity: 0.55,
        interactive: false,
      }).addTo(group)
    }
  }, [grid.data, showZones])

  // station pins
  useEffect(() => {
    const group = pins.current
    if (!group) return
    group.clearLayers()
    for (const p of stations.data?.stations ?? []) {
      L.marker([p.lat, p.lon], {
        icon: L.divIcon({ className: '', html: pinHtml(p), iconSize: [34, 34], iconAnchor: [17, 17] }),
        title: pinLabel(p),
        alt: pinLabel(p),
        keyboard: true,
      })
        .bindTooltip(pinLabel(p), { direction: 'top', offset: [0, -16] })
        .addTo(group)
    }
  }, [stations.data])

  const btn =
    'focus-ring glass-card grid h-[44px] w-[44px] place-items-center rounded-full text-ink hover:bg-white'

  return (
    // `isolate`: Leaflet's panes use z-index 400-700; keep them inside the map so overlays like
    // the Places drawer always sit on top.
    <div className={clsx('relative isolate overflow-hidden rounded-card', className)}>
      <div ref={el} className="vk-map h-full w-full" aria-label="Pollution map" role="region" />

      {/* legend */}
      <div className="glass-card pointer-events-auto absolute bottom-3 left-3 z-[500] hidden max-w-[300px] p-3 text-[11px] sm:block">
        <p className="mb-1 font-medium text-ink">PM2.5 zones (CAMS, Estimated)</p>
        {grid.isError && <p className="mb-1 text-stale">Zones unavailable right now</p>}
        <div className="flex h-2 overflow-hidden rounded-full" aria-hidden>
          {AQI_KEYS.map((k) => (
            <span key={k} className="flex-1" style={{ background: aqiVar(k) }} />
          ))}
        </div>
        <div className="mt-0.5 flex justify-between text-ink-muted">
          <span>{AQI_LABELS.good}</span>
          <span>{AQI_LABELS.severe}</span>
        </div>
        <ul className="mt-2 space-y-1 text-ink-muted">
          <li className="flex items-center gap-2">
            <span aria-hidden className="h-3 w-3 rounded-full bg-white outline outline-2 outline-ink" /> Station, measured
          </li>
          <li className="flex items-center gap-2">
            <span aria-hidden className="h-3 w-3 rounded-full bg-white outline-dashed outline-2 outline-ink" /> Estimated from nearby stations
          </li>
          <li className="flex items-center gap-2">
            <span aria-hidden className="grid h-3 w-3 place-items-center rounded-full bg-[#c7ced5] text-[8px] font-bold text-ink">!</span> Not reporting
          </li>
        </ul>
      </div>

      {/* controls */}
      <div className="absolute bottom-3 right-3 z-[500] flex flex-col gap-2 pb-5">
        <button
          type="button"
          className={clsx(btn, !showZones && 'opacity-60')}
          aria-pressed={showZones}
          aria-label={showZones ? 'Hide PM2.5 zones' : 'Show PM2.5 zones'}
          title="PM2.5 zones"
          onClick={() => setShowZones((s) => !s)}
        >
          <Layers aria-hidden className="h-4 w-4" />
        </button>
        <button type="button" className={btn} aria-label="Zoom in" onClick={() => map.current?.zoomIn()}>
          <Plus aria-hidden className="h-4 w-4" />
        </button>
        <button type="button" className={btn} aria-label="Zoom out" onClick={() => map.current?.zoomOut()}>
          <Minus aria-hidden className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={btn}
          aria-label="Back to city centre"
          onClick={() => district && map.current?.setView([district.lat, district.lon], ZOOM)}
        >
          <Crosshair aria-hidden className="h-4 w-4" />
        </button>
      </div>
      {stations.data && stations.data.stations.length === 0 && (
        <p className="glass-card absolute left-3 top-3 z-[500] px-3 py-2 text-[12px] text-ink-muted">
          No CPCB station in this district: values shown are model estimates.
        </p>
      )}
    </div>
  )
}
