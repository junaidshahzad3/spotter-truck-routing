// Mirrors the backend contract of POST /api/plan (see backend/routing/service.py).

export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'
export type Interval = 10 | 25 | 50

export interface Place {
  lat: number
  lon: number
  label: string
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string // ISO-8601 with UTC offset
  load_weight_lbs: number
  interval_miles: Interval
  include_heatmap?: boolean
}

export interface CheckpointWeather {
  wind_mph: number
  gust_mph: number
  rain_in_h: number
  snow_in_h: number
  forecast_hour: string | null
}

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  eta: string
  start_mi: number
  end_mi: number
  geometry_range: [number, number]
  weather: CheckpointWeather | null
  risk: RiskLevel | null
  score: number | null
  reasons: string[]
}

export interface RouteSummary {
  no_travel_mi: number
  severe_mi: number
  high_mi: number
  moderate_mi: number
  low_mi: number
  unknown_mi: number
  avg_risk: number
  max_risk: RiskLevel | null
}

export interface PlannedRoute {
  id: string
  name: string
  rank: number
  distance_mi: number
  duration_s: number
  arrival: string
  geometry: [number, number][] // [lon, lat]
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export interface Heatmap {
  step_deg: number
  hours: number[]
  times: string[]
  cells: { lat: number; lon: number; risk: (number | null)[] }[]
}

export interface PlanResponse {
  recommended_route_id: string
  recommendation_reason: string
  departure: string
  load_weight_lbs: number
  interval_miles: Interval
  origin: Place
  destination: Place
  routes: PlannedRoute[]
  heatmap: Heatmap | null
  warnings: string[]
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown }
}
