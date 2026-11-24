import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'

import type { FinderPlace } from '../../lib/api'

const pin = (html: string) => L.divIcon({ className: '', html, iconSize: [34, 34], iconAnchor: [17, 17] })

interface Props {
  origin: { name: string; lat: number; lon: number } | undefined
  places: FinderPlace[]
  selected: string | null
  route: [number, number][] | undefined
  onSelect: (id: string) => void
}

/** Start pin (green), numbered destination pins, and the selected route line. */
export function FinderMap({ origin, places, selected, route, onSelect }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layer = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!el.current || map.current) return
    const m = L.map(el.current, { zoomControl: true, center: [22.5, 79], zoom: 5 })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      className: 'vk-tiles',
      attribution: '© OpenStreetMap contributors · Routes: OSRM',
    }).addTo(m)
    m.attributionControl.setPrefix(false)
    layer.current = L.layerGroup().addTo(m)
    map.current = m
    return () => {
      m.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    const m = map.current
    const g = layer.current
    if (!m || !g || !origin) return
    g.clearLayers()
    const bounds: L.LatLngExpression[] = [[origin.lat, origin.lon]]
    L.marker([origin.lat, origin.lon], {
      icon: L.divIcon({ className: '', html: '<div class="vk-user-pin"><span></span></div>', iconSize: [44, 44], iconAnchor: [22, 22] }),
      title: `Start: ${origin.name}`,
      zIndexOffset: 1000,
    }).addTo(g)
    places.forEach((p, i) => {
      const active = p.id === selected
      L.marker([p.lat, p.lon], {
        icon: pin(`<div class="vk-pin" style="background:${active ? '#17212b' : '#fff'};color:${active ? '#fff' : '#17212b'};border:2px solid #17212b">${i + 1}</div>`),
        title: `${i + 1}. ${p.name}`,
        keyboard: true,
      })
        .on('click', () => onSelect(p.id))
        .addTo(g)
      bounds.push([p.lat, p.lon])
    })
    if (route?.length) {
      L.polyline(route, { color: '#1f9d55', weight: 5, opacity: 0.85 }).addTo(g)
      route.forEach((pt) => bounds.push(pt))
    }
    const focus = route?.length ? route : bounds
    m.fitBounds(L.latLngBounds(focus as L.LatLngExpression[]), { padding: [40, 40], maxZoom: 12 })
  }, [origin, places, selected, route, onSelect])

  return <div ref={el} className="vk-map relative isolate h-full min-h-[360px] w-full rounded-card" role="region" aria-label="Finder map" />
}
