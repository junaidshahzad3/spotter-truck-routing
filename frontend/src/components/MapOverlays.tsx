import { useEffect, useState } from 'react'
import type { Heatmap } from '../api/types'
import { formatDateTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS } from '../lib/risk'

export function Legend() {
  const keys = ['low', 'moderate', 'high', 'severe', 'no_travel', 'unknown'] as const
  return (
    <div className="rounded-xl border border-slate-200/80 bg-white/95 px-3 py-2 shadow-md backdrop-blur">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Weather risk</div>
      <ul className="space-y-1">
        {keys.map((k) => (
          <li key={k} className="flex items-center gap-2 text-xs text-slate-700">
            <span className="h-1.5 w-5 rounded-full" style={{ background: RISK_COLORS[k] }} />
            {RISK_LABELS[k]}
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
        <span className="h-1.5 w-5 rounded-full bg-slate-500/60" /> Alternative route
      </div>
    </div>
  )
}

interface SliderProps {
  heatmap: Heatmap
  hour: number
  onHour: (h: number) => void
  visible: boolean
  onVisible: (v: boolean) => void
}

export function HeatmapSlider({ heatmap, hour, onHour, visible, onVisible }: SliderProps) {
  const [playing, setPlaying] = useState(false)
  const max = heatmap.hours.length - 1

  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => onHour((hour + 1) % (max + 1)), 450)
    return () => clearInterval(t)
  }, [playing, hour, max, onHour])

  return (
    <div className="rounded-xl border border-slate-200/80 bg-white/95 p-3 shadow-lg backdrop-blur">
      <div className="mb-2 flex items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            className="accent-sky-600"
            checked={visible}
            onChange={(e) => onVisible(e.target.checked)}
          />
          Weather heatmap
        </label>
        <div className="text-xs tabular-nums text-slate-600">
          <span className="font-semibold text-slate-900">+{hour} h</span> · {formatDateTime(heatmap.times[hour])}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={!visible}
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? 'Pause' : 'Play'}
          className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-900 text-white disabled:opacity-40"
        >
          {playing ? (
            <svg viewBox="0 0 20 20" className="size-3.5" fill="currentColor"><path d="M5 4h3v12H5zM12 4h3v12h-3z" /></svg>
          ) : (
            <svg viewBox="0 0 20 20" className="size-3.5" fill="currentColor"><path d="M6 4l10 6-10 6z" /></svg>
          )}
        </button>
        <input
          type="range"
          min={0}
          max={max}
          step={1}
          value={hour}
          disabled={!visible}
          onChange={(e) => {
            setPlaying(false)
            onHour(Number(e.target.value))
          }}
          aria-label="Hours after departure"
          className="w-full accent-sky-600"
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-400">
        <span>Departure</span>
        <span>+24 h</span>
        <span>+{max} h</span>
      </div>
    </div>
  )
}
