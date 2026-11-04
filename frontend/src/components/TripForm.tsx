import { useState } from 'react'
import type { Interval, Place, PlanRequest } from '../api/types'
import { localInputToIso, nextFullHour, toLocalInput } from '../lib/format'
import { PlaceInput } from './PlaceInput'

const INTERVALS: Interval[] = [10, 25, 50]
const MAX_LOAD = 80_000
const MAX_DAYS_AHEAD = 15

const EXAMPLE = {
  origin: { label: 'Dallas, Texas', lat: 32.7767, lon: -96.797 },
  destination: { label: 'Denver, Colorado', lat: 39.7392, lon: -104.9903 },
}

const Pin = ({ className }: { className: string }) => (
  <svg viewBox="0 0 20 20" className={`size-4 ${className}`} fill="currentColor" aria-hidden>
    <path d="M10 18s6-5.3 6-10a6 6 0 1 0-12 0c0 4.7 6 10 6 10Zm0-7.5A2.5 2.5 0 1 1 10 5.5a2.5 2.5 0 0 1 0 5Z" />
  </svg>
)

interface Props {
  pending: boolean
  onSubmit: (req: PlanRequest) => void
}

type Errors = Partial<Record<'origin' | 'destination' | 'departure' | 'weight', string>>

export function TripForm({ pending, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(() => toLocalInput(nextFullHour()))
  const [weight, setWeight] = useState('40000')
  const [interval, setIntervalMiles] = useState<Interval>(25)
  const [errors, setErrors] = useState<Errors>({})

  const [[minInput, maxInput]] = useState(() => [
    toLocalInput(new Date(Date.now() - 60 * 60_000)),
    toLocalInput(new Date(Date.now() + MAX_DAYS_AHEAD * 86_400_000)),
  ])

  const validate = (): Errors => {
    const e: Errors = {}
    if (!origin) e.origin = 'Choose an origin from the suggestions.'
    if (!destination) e.destination = 'Choose a destination from the suggestions.'
    if (origin && destination && origin.lat === destination.lat && origin.lon === destination.lon)
      e.destination = 'Destination must differ from origin.'
    const t = new Date(departure).getTime()
    if (!departure || Number.isNaN(t)) e.departure = 'Enter a departure date and time.'
    else if (t < Date.now() - 60 * 60_000) e.departure = 'Departure can’t be in the past.'
    else if (t > Date.now() + MAX_DAYS_AHEAD * 86_400_000)
      e.departure = `Forecasts only reach ${MAX_DAYS_AHEAD} days ahead.`
    const w = Number(weight)
    if (weight.trim() === '' || !Number.isFinite(w) || w < 0 || w > MAX_LOAD)
      e.weight = `Enter a load between 0 and ${MAX_LOAD.toLocaleString()} lbs.`
    return e
  }

  const submit = (ev: React.FormEvent) => {
    ev.preventDefault()
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length || !origin || !destination) return
    onSubmit({
      origin,
      destination,
      departure: localInputToIso(departure),
      load_weight_lbs: Number(weight),
      interval_miles: interval,
    })
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      <div className="relative space-y-3">
        <PlaceInput
          label="Origin"
          value={origin}
          onChange={setOrigin}
          placeholder="City or address"
          error={errors.origin}
          icon={<Pin className="text-emerald-600" />}
        />
        <PlaceInput
          label="Destination"
          value={destination}
          onChange={setDestination}
          placeholder="City or address"
          error={errors.destination}
          icon={<Pin className="text-rose-600" />}
        />
        <button
          type="button"
          title="Swap origin and destination"
          aria-label="Swap origin and destination"
          onClick={() => {
            setOrigin(destination)
            setDestination(origin)
          }}
          className="absolute right-2 top-[3.65rem] z-10 grid size-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm hover:text-sky-600"
        >
          <svg viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M7 3v14M7 17l-3-3M7 17l3-3M13 17V3M13 3l-3 3M13 3l3 3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="departure" className="mb-1 block text-xs font-medium text-slate-600">
            Departure
          </label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            min={minInput}
            max={maxInput}
            onChange={(e) => setDeparture(e.target.value)}
            aria-invalid={!!errors.departure}
            className={`h-10 w-full rounded-lg border bg-white px-2 text-sm text-slate-900 shadow-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40 ${
              errors.departure ? 'border-red-400' : 'border-slate-200'
            }`}
          />
        </div>
        <div>
          <label htmlFor="weight" className="mb-1 block text-xs font-medium text-slate-600">
            Load weight
          </label>
          <div
            className={`flex h-10 items-center rounded-lg border bg-white pr-3 shadow-sm focus-within:border-sky-500 focus-within:ring-2 focus-within:ring-sky-500/40 ${
              errors.weight ? 'border-red-400' : 'border-slate-200'
            }`}
          >
            <input
              id="weight"
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD}
              step={500}
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              aria-invalid={!!errors.weight}
              className="h-full w-full rounded-lg bg-transparent px-3 text-sm text-slate-900 outline-none"
            />
            <span className="text-xs text-slate-400">lbs</span>
          </div>
        </div>
      </div>
      {(errors.departure || errors.weight) && (
        <p className="text-xs text-red-600">{errors.departure ?? errors.weight}</p>
      )}

      <div>
        <span className="mb-1 block text-xs font-medium text-slate-600">Weather checkpoint every</span>
        <div role="radiogroup" className="grid grid-cols-3 rounded-lg bg-slate-100 p-1">
          {INTERVALS.map((v) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={interval === v}
              onClick={() => setIntervalMiles(v)}
              className={`rounded-md py-1.5 text-sm font-medium transition ${
                interval === v ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {v} mi
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-slate-900 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"
        >
          {pending && (
            <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          )}
          {pending ? 'Planning routes…' : 'Plan routes'}
        </button>
        <button
          type="button"
          onClick={() => {
            setOrigin(EXAMPLE.origin)
            setDestination(EXAMPLE.destination)
            setErrors({})
          }}
          className="h-10 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:bg-slate-50"
        >
          Example
        </button>
      </div>
    </form>
  )
}
