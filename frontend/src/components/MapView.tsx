import type { FeatureCollection } from 'geojson'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource, LngLatBoundsLike } from 'maplibre-gl'
// MapLibre v6 locates its worker via import.meta.url, which Vite's dep pre-bundling breaks.
// Let Vite bundle the worker (with its shared chunk) and hand MapLibre the URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef, useState } from 'react'
import type { Checkpoint, PlanResponse } from '../api/types'
import { formatDateTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS, levelFromScore, riskKey } from '../lib/risk'

maplibregl.setWorkerUrl(workerUrl)

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

const riskColorExpr: maplibregl.ExpressionSpecification = [
  'match',
  ['get', 'risk'],
  'low', RISK_COLORS.low,
  'moderate', RISK_COLORS.moderate,
  'high', RISK_COLORS.high,
  'severe', RISK_COLORS.severe,
  'no_travel', RISK_COLORS.no_travel,
  RISK_COLORS.unknown,
]

interface Props {
  plan: PlanResponse | null
  selectedId: string | null
  onSelectRoute: (id: string) => void
  hovered: number | null
  focusRequest: { index: number; nonce: number } | null
  heatmapHour: number
  showHeatmap: boolean
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

function popupHtml(cp: Checkpoint): string {
  const key = riskKey(cp.risk)
  const w = cp.weather
  const rows = w
    ? `<div class="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-slate-600 mt-1">
         <span>Wind</span><span class="text-right tabular-nums">${w.wind_mph.toFixed(0)} mph</span>
         <span>Gusts</span><span class="text-right tabular-nums">${w.gust_mph.toFixed(0)} mph</span>
         <span>Rain</span><span class="text-right tabular-nums">${w.rain_in_h.toFixed(2)} in/h</span>
         <span>Snow</span><span class="text-right tabular-nums">${w.snow_in_h.toFixed(2)} in/h</span>
       </div>`
    : ''
  const reasons = cp.reasons.length
    ? `<ul class="mt-1.5 space-y-0.5 text-xs text-slate-700">${cp.reasons
        .map((r) => `<li>• ${esc(r)}</li>`)
        .join('')}</ul>`
    : ''
  return `<div class="min-w-48">
    <div class="flex items-center justify-between gap-3">
      <strong class="text-sm text-slate-900">Mile ${Math.round(cp.mile)}</strong>
      <span class="text-xs font-semibold" style="color:${RISK_COLORS[key]}">${RISK_LABELS[key]}</span>
    </div>
    <div class="text-xs text-slate-500">ETA ${esc(formatDateTime(cp.eta))}</div>
    ${rows}${reasons}
  </div>`
}

export function MapView({
  plan,
  selectedId,
  onSelectRoute,
  hovered,
  focusRequest,
  heatmapHour,
  showHeatmap,
}: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const planRef = useRef<PlanResponse | null>(null)
  const selectRef = useRef(onSelectRoute)
  const selectedRef = useRef<string | null>(null)
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)

  // Latest props for the map's event handlers (registered once).
  useEffect(() => {
    planRef.current = plan
    selectRef.current = onSelectRoute
    selectedRef.current = selectedId
  })

  // ---- init once
  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE_URL,
      center: [-98.5, 39.5],
      zoom: 3.6,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('error', (e) => {
      if (!map.isStyleLoaded()) setMapError(e.error?.message ?? 'Map failed to load')
    })

    map.on('load', () => {
      for (const id of ['heatmap', 'routes', 'segments', 'checkpoints', 'endpoints']) {
        map.addSource(id, { type: 'geojson', data: EMPTY })
      }
      map.addLayer({
        id: 'heatmap-fill',
        type: 'fill',
        source: 'heatmap',
        paint: { 'fill-color': riskColorExpr, 'fill-opacity': ['case', ['==', ['get', 'risk'], 'low'], 0.06, 0.4] },
      })
      map.addLayer({
        id: 'routes-alt',
        type: 'line',
        source: 'routes',
        filter: ['!', ['get', 'selected']],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#64748b', 'line-width': 4, 'line-opacity': 0.55 },
      })
      map.addLayer({
        id: 'routes-casing',
        type: 'line',
        source: 'routes',
        filter: ['get', 'selected'],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#0f172a', 'line-width': 9, 'line-opacity': 0.85 },
      })
      map.addLayer({
        id: 'segments-line',
        type: 'line',
        source: 'segments',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': riskColorExpr, 'line-width': 5.5 },
      })
      map.addLayer({
        id: 'routes-hit',
        type: 'line',
        source: 'routes',
        paint: { 'line-color': '#000', 'line-width': 18, 'line-opacity': 0 },
      })
      map.addLayer({
        id: 'checkpoints-circle',
        type: 'circle',
        source: 'checkpoints',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.5, 8, 6],
          'circle-color': riskColorExpr,
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 1.5,
        },
      })
      map.addLayer({
        id: 'checkpoints-hover',
        type: 'circle',
        source: 'checkpoints',
        filter: ['==', ['get', 'index'], -1],
        paint: {
          'circle-radius': 10,
          'circle-color': riskColorExpr,
          'circle-stroke-color': '#0f172a',
          'circle-stroke-width': 2.5,
        },
      })
      map.addLayer({
        id: 'endpoints-circle',
        type: 'circle',
        source: 'endpoints',
        paint: {
          'circle-radius': 8,
          'circle-color': ['match', ['get', 'kind'], 'origin', '#059669', '#e11d48'],
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 3,
        },
      })

      map.on('click', 'routes-hit', (e) => {
        if (map.queryRenderedFeatures(e.point, { layers: ['checkpoints-circle'] }).length) return
        const id = e.features?.[0]?.properties?.id as string | undefined
        if (id) selectRef.current(id)
      })
      map.on('click', 'checkpoints-circle', (e) => {
        const index = e.features?.[0]?.properties?.index as number | undefined
        const route = planRef.current?.routes.find((r) => r.id === selectedRef.current)
        const cp = route?.checkpoints.find((c) => c.index === index)
        if (cp) showPopup(cp)
      })
      for (const layer of ['routes-hit', 'checkpoints-circle']) {
        map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
        map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
      }
      setReady(true)
    })

    function showPopup(cp: Checkpoint) {
      popupRef.current?.remove()
      popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: '280px', offset: 10 })
        .setLngLat([cp.lon, cp.lat])
        .setHTML(popupHtml(cp))
        .addTo(map)
    }
    ;(map as unknown as { _showPopup: typeof showPopup })._showPopup = showPopup

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // ---- routes, segments, checkpoints, endpoints
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const src = (id: string) => map.getSource(id) as GeoJSONSource
    popupRef.current?.remove()
    if (!plan) {
      for (const id of ['routes', 'segments', 'checkpoints', 'endpoints']) src(id).setData(EMPTY)
      return
    }
    const selected = plan.routes.find((r) => r.id === selectedId) ?? plan.routes[0]
    // Draw unselected routes first so the selected one sits on top.
    const ordered = [...plan.routes].sort((a, b) => Number(a.id === selected.id) - Number(b.id === selected.id))
    src('routes').setData({
      type: 'FeatureCollection',
      features: ordered.map((r) => ({
        type: 'Feature',
        properties: { id: r.id, selected: r.id === selected.id },
        geometry: { type: 'LineString', coordinates: r.geometry },
      })),
    })
    src('segments').setData({
      type: 'FeatureCollection',
      features: selected.checkpoints.map((cp) => {
        const [lo, hi] = cp.geometry_range
        let coords = selected.geometry.slice(lo, hi)
        if (coords.length < 2) coords = selected.geometry.slice(Math.max(0, lo - 1), lo + 2)
        return {
          type: 'Feature',
          properties: { risk: riskKey(cp.risk), index: cp.index },
          geometry: { type: 'LineString', coordinates: coords },
        }
      }),
    })
    src('checkpoints').setData({
      type: 'FeatureCollection',
      features: selected.checkpoints.map((cp) => ({
        type: 'Feature',
        properties: { risk: riskKey(cp.risk), index: cp.index },
        geometry: { type: 'Point', coordinates: [cp.lon, cp.lat] },
      })),
    })
    src('endpoints').setData({
      type: 'FeatureCollection',
      features: [
        { kind: 'origin', p: plan.origin },
        { kind: 'destination', p: plan.destination },
      ].map(({ kind, p }) => ({
        type: 'Feature',
        properties: { kind },
        geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      })),
    })
  }, [ready, plan, selectedId])

  // ---- fit bounds when a new plan arrives
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !plan) return
    const all = plan.routes.flatMap((r) => r.geometry)
    const lons = all.map((c) => c[0])
    const lats = all.map((c) => c[1])
    const bounds: LngLatBoundsLike = [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ]
    const narrow = map.getContainer().clientWidth < 640
    map.fitBounds(bounds, { padding: narrow ? 40 : { top: 60, bottom: 160, left: 220, right: 60 }, duration: 900 })
  }, [ready, plan])

  // ---- heatmap frame
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const hm = plan?.heatmap
    const src = map.getSource('heatmap') as GeoJSONSource
    if (!hm || !showHeatmap) {
      src.setData(EMPTY)
      return
    }
    const half = hm.step_deg / 2
    src.setData({
      type: 'FeatureCollection',
      features: hm.cells
        .filter((c) => c.risk[heatmapHour] !== null && c.risk[heatmapHour] !== undefined)
        .map((c) => ({
          type: 'Feature',
          properties: { risk: levelFromScore(c.risk[heatmapHour]) },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [c.lon - half, c.lat - half],
                [c.lon + half, c.lat - half],
                [c.lon + half, c.lat + half],
                [c.lon - half, c.lat + half],
                [c.lon - half, c.lat - half],
              ],
            ],
          },
        })),
    })
  }, [ready, plan, heatmapHour, showHeatmap])

  // ---- hover highlight from the list
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    map.setFilter('checkpoints-hover', ['==', ['get', 'index'], hovered ?? -1])
  }, [ready, hovered])

  // ---- focus a checkpoint (from the list)
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !plan || !focusRequest) return
    const route = plan.routes.find((r) => r.id === selectedId)
    const cp = route?.checkpoints.find((c) => c.index === focusRequest.index)
    if (!cp) return
    map.easeTo({ center: [cp.lon, cp.lat], zoom: Math.max(map.getZoom(), 7), duration: 600 })
    ;(map as unknown as { _showPopup: (c: Checkpoint) => void })._showPopup(cp)
  }, [ready, plan, selectedId, focusRequest])

  return (
    <div className="relative size-full">
      <div ref={container} className="size-full" />
      {mapError && (
        <div className="absolute inset-x-4 top-4 rounded-lg bg-red-50 p-3 text-sm text-red-800 shadow">
          Basemap unavailable ({mapError}). Routes still render once a plan is loaded.
        </div>
      )}
    </div>
  )
}
