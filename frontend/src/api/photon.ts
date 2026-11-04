import { useQuery } from '@tanstack/react-query'
import type { Place } from './types'

// Photon (komoot) allows typeahead use, unlike Nominatim's public API.
const PHOTON_URL = 'https://photon.komoot.io/api/'

interface PhotonFeature {
  geometry: { coordinates: [number, number] }
  properties: {
    name?: string
    street?: string
    housenumber?: string
    city?: string
    county?: string
    state?: string
    country?: string
    countrycode?: string
    osm_value?: string
    type?: string
  }
}

export function formatPhotonLabel(p: PhotonFeature['properties']): string {
  const street = p.street ? [p.housenumber, p.street].filter(Boolean).join(' ') : undefined
  const parts = [p.name ?? street, p.city !== p.name ? p.city : undefined, p.state]
  if (p.countrycode && p.countrycode.toUpperCase() !== 'US') parts.push(p.country)
  return [...new Set(parts.filter(Boolean))].join(', ')
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const url = new URL(PHOTON_URL)
  url.searchParams.set('q', query)
  url.searchParams.set('limit', '6')
  url.searchParams.set('lang', 'en')
  // Gentle bias toward the continental US (trucking context) without excluding elsewhere.
  url.searchParams.set('lat', '39.5')
  url.searchParams.set('lon', '-98.35')
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`Place search failed (${res.status})`)
  const data = (await res.json()) as { features: PhotonFeature[] }
  const seen = new Set<string>()
  return data.features
    .map((f) => ({
      lon: f.geometry.coordinates[0],
      lat: f.geometry.coordinates[1],
      label: formatPhotonLabel(f.properties),
    }))
    .filter((p) => p.label && !seen.has(p.label) && seen.add(p.label))
}

export function usePlaceSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: ['photon', q],
    queryFn: ({ signal }) => searchPlaces(q, signal),
    enabled: q.length >= 3,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
