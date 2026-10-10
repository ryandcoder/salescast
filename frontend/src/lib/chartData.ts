// Pure data shaping for the charts (no React), unit-tested with `npm test`.
import type { ForecastPoint, HistoryPoint, TestPoint, TrendPoint } from '../services/api.ts'
import { MONTHS } from './format.ts'

export type Metric = 'revenue' | 'units' | 'orders'

export interface OverviewRow {
  period: string
  value: number | null
  movingAvg: number | null
  trend: number | null
  partial: boolean
}

/** Revenue carries the 3-period moving average and trend line from the API; units and orders are plain lines. */
export function buildOverviewRows(series: TrendPoint[], metric: Metric): OverviewRow[] {
  return series.map((p) => ({
    period: p.period,
    value: p[metric],
    movingAvg: metric === 'revenue' ? p.moving_avg_3 : null,
    trend: metric === 'revenue' ? p.trend : null,
    partial: p.partial,
  }))
}

export interface ForecastRow {
  period: string
  actual: number | null
  forecast: number | null
  lower: number | null
  /** upper - lower: the height of the interval band when stacked on top of `lower`. */
  band: number | null
  upper: number | null
  isForecast: boolean
}

/**
 * History rows followed by forecast rows. The last actual month also gets a zero-width forecast
 * point so the dashed forecast line starts exactly where the solid actual line ends.
 */
export function buildForecastRows(history: HistoryPoint[], forecast: ForecastPoint[]): ForecastRow[] {
  const rows: ForecastRow[] = history.map((h) => ({
    period: h.period,
    actual: h.revenue,
    forecast: null,
    lower: null,
    band: null,
    upper: null,
    isForecast: false,
  }))
  const last = rows[rows.length - 1]
  if (last && last.actual !== null && forecast.length > 0) {
    last.forecast = last.actual
    last.lower = last.actual
    last.upper = last.actual
    last.band = 0
  }
  for (const f of forecast) {
    rows.push({
      period: f.period,
      actual: null,
      forecast: f.forecast,
      lower: f.lower,
      band: Math.max(0, f.upper - f.lower),
      upper: f.upper,
      isForecast: true,
    })
  }
  return rows
}

export function firstForecastPeriod(rows: ForecastRow[]): string | null {
  return rows.find((r) => r.isForecast)?.period ?? null
}

export function lastActualPeriod(rows: ForecastRow[]): string | null {
  for (let i = rows.length - 1; i >= 0; i--) if (!rows[i].isForecast) return rows[i].period
  return null
}

/** One row per calendar month, one column per year, for the seasonal overlay chart. */
export function buildSeasonalRows(byYear: Record<string, (number | null)[]>, maxYears = 4) {
  const years = Object.keys(byYear).sort().slice(-maxYears)
  const rows = MONTHS.map((month, i) => {
    const row: Record<string, string | number | null> = { month }
    for (const y of years) row[y] = byYear[y]?.[i] ?? null
    return row
  })
  return { years, rows }
}

export function testRows(series: TestPoint[]): TestPoint[] {
  return series.filter((r) => r.actual !== null)
}
