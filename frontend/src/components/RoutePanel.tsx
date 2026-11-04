import type { PlanResponse, PlannedRoute } from '../api/types'
import { formatDateTime, formatDuration, formatMiles, formatShortTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS, riskKey } from '../lib/risk'

function RiskBar({ route }: { route: PlannedRoute }) {
  const s = route.summary
  const parts = [
    ['low', s.low_mi],
    ['moderate', s.moderate_mi],
    ['high', s.high_mi],
    ['severe', s.severe_mi],
    ['unknown', s.unknown_mi],
  ] as const
  const total = parts.reduce((a, [, v]) => a + v, 0) || 1
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
      {parts.map(([k, v]) =>
        v > 0 ? (
          <div key={k} style={{ width: `${(v / total) * 100}%`, background: RISK_COLORS[k] }} />
        ) : null,
      )}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${tone ?? 'text-slate-800'}`}>{value}</div>
    </div>
  )
}

function RouteCard({
  route,
  recommended,
  selected,
  onSelect,
}: {
  route: PlannedRoute
  recommended: boolean
  selected: boolean
  onSelect: () => void
}) {
  const s = route.summary
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-xl border p-3 text-left transition ${
        selected
          ? 'border-sky-500 bg-sky-50/60 ring-2 ring-sky-500/20'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">{route.name}</span>
          {recommended && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
              Recommended
            </span>
          )}
        </div>
        <span className="text-xs text-slate-500">
          {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)}
        </span>
      </div>
      <RiskBar route={route} />
      <div className="mt-2 grid grid-cols-4 gap-2">
        <Stat label="Severe" value={formatMiles(s.severe_mi)} tone={s.severe_mi ? 'text-red-600' : undefined} />
        <Stat label="High" value={formatMiles(s.high_mi)} tone={s.high_mi ? 'text-orange-600' : undefined} />
        <Stat label="Avg risk" value={s.avg_risk.toFixed(2)} />
        <Stat label="Arrive" value={formatShortTime(route.arrival)} />
      </div>
    </button>
  )
}

interface Props {
  plan: PlanResponse
  selectedId: string
  onSelect: (id: string) => void
  hovered: number | null
  onHover: (index: number | null) => void
  onFocusCheckpoint: (index: number) => void
}

export function RoutePanel({ plan, selectedId, onSelect, hovered, onHover, onFocusCheckpoint }: Props) {
  const selected = plan.routes.find((r) => r.id === selectedId) ?? plan.routes[0]
  const recommended = plan.routes.find((r) => r.id === plan.recommended_route_id)

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
          Recommended: {recommended?.name}
        </div>
        <p className="mt-1 text-sm text-emerald-900">{plan.recommendation_reason}</p>
        <p className="mt-1 text-xs text-emerald-700/80">
          Ranked by fewest Severe miles, then High miles, then average risk, then drive time.
        </p>
      </section>

      {plan.warnings.length > 0 && (
        <section className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {plan.warnings.map((w) => (
            <p key={w}>⚠ {w}</p>
          ))}
        </section>
      )}

      <section className="space-y-2">
        {plan.routes.map((r) => (
          <RouteCard
            key={r.id}
            route={r}
            recommended={r.id === plan.recommended_route_id}
            selected={r.id === selected.id}
            onSelect={() => onSelect(r.id)}
          />
        ))}
      </section>

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            {selected.name} checkpoints
          </h2>
          <span className="text-xs text-slate-500">
            every {plan.interval_miles} mi · {selected.checkpoints.length} points
          </span>
        </div>
        <ol className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {selected.checkpoints.map((cp) => {
            const key = riskKey(cp.risk)
            return (
              <li key={cp.index}>
                <button
                  type="button"
                  onMouseEnter={() => onHover(cp.index)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(cp.index)}
                  onBlur={() => onHover(null)}
                  onClick={() => onFocusCheckpoint(cp.index)}
                  className={`flex w-full items-start gap-3 px-3 py-2 text-left transition ${
                    hovered === cp.index ? 'bg-slate-50' : ''
                  }`}
                >
                  <span
                    className="mt-1 size-2.5 shrink-0 rounded-full ring-2 ring-white"
                    style={{ background: RISK_COLORS[key] }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-medium tabular-nums text-slate-800">
                        Mile {Math.round(cp.mile)}
                      </span>
                      <span className="text-xs tabular-nums text-slate-500">{formatDateTime(cp.eta)}</span>
                    </span>
                    <span className="flex items-baseline justify-between gap-2 text-xs">
                      <span className="truncate text-slate-500">
                        {cp.reasons[0] ??
                          (cp.weather
                            ? `Wind ${Math.round(cp.weather.wind_mph)} mph · gust ${Math.round(cp.weather.gust_mph)}`
                            : '')}
                      </span>
                      <span className="shrink-0 font-semibold" style={{ color: RISK_COLORS[key] }}>
                        {RISK_LABELS[key]}
                      </span>
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </section>
    </div>
  )
}
