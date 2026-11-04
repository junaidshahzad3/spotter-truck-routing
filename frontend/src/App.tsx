import { useCallback, useState } from 'react'
import { usePlan } from './api/client'
import type { PlanRequest } from './api/types'
import { HeatmapSlider, Legend } from './components/MapOverlays'
import { MapView } from './components/MapView'
import { RoutePanel } from './components/RoutePanel'
import { TripForm } from './components/TripForm'

function Skeleton() {
  return (
    <div className="space-y-3" aria-busy>
      <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-100" />
      ))}
      <p className="text-center text-xs text-slate-500">
        Fetching truck routes and forecasts along each one… this can take up to ~15 s.
      </p>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-600">
      <p className="font-medium text-slate-800">How it works</p>
      <ol className="mt-2 list-decimal space-y-1 pl-4">
        <li>We fetch up to 3 truck routes for your trip.</li>
        <li>Every 10/25/50 miles we look up the forecast for the hour the truck will be there.</li>
        <li>Wind, rain and snow set each stretch’s risk (Low → No Travel); strong wind with a heavy load is rated higher.</li>
        <li>The safest route is recommended; drag the heatmap slider to see conditions over 48 h.</li>
      </ol>
    </div>
  )
}

export default function App() {
  const plan = usePlan()
  const [lastRequest, setLastRequest] = useState<PlanRequest | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [focus, setFocus] = useState<{ index: number; nonce: number } | null>(null)
  const [hour, setHour] = useState(0)
  const [showHeatmap, setShowHeatmap] = useState(true)

  const submit = useCallback(
    (req: PlanRequest) => {
      setLastRequest(req)
      plan.mutate(req, {
        onSuccess: (data) => {
          setSelectedId(data.recommended_route_id)
          setHour(0)
          setHovered(null)
        },
      })
    },
    [plan],
  )

  const data = plan.data ?? null
  const err = plan.error

  return (
    <div className="flex h-dvh flex-col bg-slate-50 text-slate-900 md:flex-row">
      <aside className="order-2 flex min-h-0 flex-1 flex-col border-slate-200 bg-white md:order-1 md:w-[420px] md:flex-none md:border-r">
        <header className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <div className="grid size-9 place-items-center rounded-lg bg-slate-900">
            <svg viewBox="0 0 32 32" className="size-6" fill="none" stroke="#38bdf8" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 21h3l3-9 4 12 3-7h7" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-semibold leading-tight">Weather-Aware Truck Routing</h1>
            <p className="text-xs text-slate-500">Pick the route the forecast is kindest to.</p>
          </div>
        </header>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <TripForm pending={plan.isPending} onSubmit={submit} />
          {err && (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <p className="font-medium">Couldn’t plan this trip</p>
              <p className="mt-0.5">{err.message}</p>
              {err.retryable && lastRequest && (
                <button
                  type="button"
                  onClick={() => submit(lastRequest)}
                  className="mt-2 rounded-md bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700"
                >
                  Try again
                </button>
              )}
            </div>
          )}
          {plan.isPending ? (
            <Skeleton />
          ) : data && selectedId ? (
            <RoutePanel
              plan={data}
              selectedId={selectedId}
              onSelect={setSelectedId}
              hovered={hovered}
              onHover={setHovered}
              onFocusCheckpoint={(index) => {
                setFocus({ index, nonce: Date.now() })
                // Jump the heatmap to the hour the truck reaches this checkpoint.
                const route = data.routes.find((r) => r.id === selectedId)
                const cp = route?.checkpoints.find((c) => c.index === index)
                if (cp && data.heatmap) {
                  const h = Math.round((Date.parse(cp.eta) - Date.parse(data.departure)) / 3_600_000)
                  setHour(Math.min(Math.max(h, 0), data.heatmap.hours.length - 1))
                }
              }}
            />
          ) : (
            !err && <EmptyState />
          )}
        </div>
        <footer className="border-t border-slate-100 px-5 py-2 text-[11px] text-slate-400">
          Routing © Valhalla / OpenStreetMap · Weather © Open-Meteo · Search © Photon
        </footer>
      </aside>

      <main className="relative order-1 h-[45dvh] shrink-0 md:order-2 md:h-auto md:flex-1">
        <MapView
          plan={data}
          selectedId={selectedId}
          onSelectRoute={setSelectedId}
          hovered={hovered}
          focusRequest={focus}
          heatmapHour={hour}
          showHeatmap={showHeatmap}
        />
        <div className="pointer-events-none absolute left-3 top-3 hidden sm:block">
          <div className="pointer-events-auto">
            <Legend />
          </div>
        </div>
        {data?.heatmap && (
          <div className="pointer-events-none absolute inset-x-2 bottom-2 flex justify-center sm:inset-x-3 sm:bottom-8">
            <div className="pointer-events-auto w-full max-w-xl">
              <HeatmapSlider
                heatmap={data.heatmap}
                hour={hour}
                onHour={setHour}
                visible={showHeatmap}
                onVisible={setShowHeatmap}
              />
            </div>
          </div>
        )}
        {plan.isPending && (
          <div className="absolute inset-0 grid place-items-center bg-white/40 backdrop-blur-[1px]">
            <div className="flex items-center gap-3 rounded-full bg-white px-4 py-2 text-sm text-slate-700 shadow-lg">
              <span className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-500" />
              Planning routes…
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
