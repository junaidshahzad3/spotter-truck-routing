import { useEffect, useId, useRef, useState } from 'react'
import { usePlaceSearch } from '../api/photon'
import type { Place } from '../api/types'

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

interface Props {
  label: string
  value: Place | null
  onChange: (p: Place | null) => void
  placeholder?: string
  error?: string
  icon: React.ReactNode
}

export function PlaceInput({ label, value, onChange, placeholder, error, icon }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const debounced = useDebounced(text, 300)
  const search = usePlaceSearch(open && text !== value?.label ? debounced : '')
  const results = search.data ?? []
  const boxRef = useRef<HTMLDivElement>(null)

  // Keep the text in sync when the value is set from outside (example trip, swap).
  const [prevValue, setPrevValue] = useState(value)
  if (value !== prevValue) {
    setPrevValue(value)
    if (value) setText(value.label)
    // Cleared from outside (e.g. swapped with an empty field): drop the stale label.
    else if (prevValue && text === prevValue.label) setText('')
  }

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const choose = (p: Place) => {
    onChange(p)
    setText(p.label)
    setOpen(false)
  }

  const showList = open && text.trim().length >= 3 && text !== value?.label
  const listId = `${id}-list`

  return (
    <div ref={boxRef} className="relative">
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      <div
        className={`flex items-center gap-2 rounded-lg border bg-white px-3 shadow-sm transition focus-within:ring-2 focus-within:ring-sky-500/40 ${
          error ? 'border-red-400' : 'border-slate-200 focus-within:border-sky-500'
        }`}
      >
        <span className="text-slate-400">{icon}</span>
        <input
          id={id}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-invalid={!!error}
          autoComplete="off"
          className="h-10 w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          placeholder={placeholder}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setOpen(true)
            setActive(0)
            if (value) onChange(null)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (!showList || !results.length) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActive((a) => (a + 1) % results.length)
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((a) => (a - 1 + results.length) % results.length)
            } else if (e.key === 'Enter') {
              e.preventDefault()
              choose(results[active])
            } else if (e.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
        {search.isFetching && (
          <span className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-500" />
        )}
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg"
        >
          {search.isError && <li className="px-3 py-2 text-red-600">Place search is unavailable.</li>}
          {!search.isFetching && !search.isError && results.length === 0 && debounced === text && (
            <li className="px-3 py-2 text-slate-500">No matches</li>
          )}
          {results.map((p, i) => (
            <li
              key={`${p.label}-${p.lat}-${p.lon}`}
              role="option"
              aria-selected={i === active}
              className={`cursor-pointer px-3 py-2 ${i === active ? 'bg-sky-50 text-sky-900' : 'text-slate-700'}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(p)
              }}
            >
              {p.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
