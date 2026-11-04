export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  if (m === 60) return `${h + 1} h`
  return h ? `${h} h ${m.toString().padStart(2, '0')} m` : `${m} m`
}

export function formatMiles(mi: number, digits = 0): string {
  return `${mi.toLocaleString(undefined, { maximumFractionDigits: digits })} mi`
}

const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const shortTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
})

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}

export function formatShortTime(iso: string): string {
  return shortTime.format(new Date(iso))
}

/** `<input type="datetime-local">` value -> ISO string with the browser's UTC offset. */
export function localInputToIso(value: string): string {
  const d = new Date(value)
  const offset = -d.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:00` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  )
}

/** Date -> value for `<input type="datetime-local">` in local time. */
export function toLocalInput(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

export function nextFullHour(from = new Date()): Date {
  const d = new Date(from)
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  return d
}
