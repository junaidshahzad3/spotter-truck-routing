import type { RiskLevel } from '../api/types'

export const RISK_LEVELS: RiskLevel[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

// Colour-blind-friendly ramp (distinguishable under deuteranopia/protanopia by lightness).
export const RISK_COLORS: Record<RiskLevel | 'unknown', string> = {
  low: '#16a34a',
  moderate: '#eab308',
  high: '#f97316',
  severe: '#dc2626',
  no_travel: '#581c87',
  unknown: '#94a3b8',
}

export const RISK_LABELS: Record<RiskLevel | 'unknown', string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
  unknown: 'No forecast',
}

export function riskKey(level: RiskLevel | null | undefined): RiskLevel | 'unknown' {
  return level ?? 'unknown'
}

export function levelFromScore(score: number | null | undefined): RiskLevel | 'unknown' {
  if (score === null || score === undefined) return 'unknown'
  return RISK_LEVELS[Math.max(0, Math.min(4, Math.round(score)))]
}
