// Typed client for the SalesCast API. Field names mirror the backend JSON exactly.
import { API_BASE } from '../config'

export interface Filters {
  date_from: string
  date_to: string
  category: string
  product: string
  region: string
}
export const EMPTY_FILTERS: Filters = { date_from: '', date_to: '', category: '', product: '', region: '' }
export const isFiltered = (f: Filters) => Object.values(f).some(Boolean)

export type Granularity = 'month' | 'quarter' | 'year'
export type Horizon = 3 | 6 | 12

export interface FilterOptions {
  categories: string[]
  regions: string[]
  products: { product: string; category: string }[]
  date_min: string | null
  date_max: string | null
}

export interface Kpis {
  total_revenue: number
  total_orders: number
  units_sold: number
  average_order_value: number | null
  average_monthly_revenue: number | null
  months_covered: number
  best_product_by_revenue: { name: string; revenue: number; units: number } | null
  best_product_by_units: { name: string; revenue: number; units: number } | null
  best_region: { name: string; revenue: number; orders: number } | null
  profit: { total_profit: number | null; profit_margin_pct: number | null } | null
  data_range: [string | null, string | null]
}
export interface DashboardResp {
  scope: { is_filtered: boolean; filters: Record<string, string> }
  kpis: Kpis
}

export interface GroupItem {
  name: string
  revenue: number
  units: number
  orders: number
  avg_price: number | null
  average_order_value: number | null
  pct_of_revenue: number
  profit: number | null
  profit_margin_pct: number | null
  category?: string
}
export interface GroupResp {
  items: GroupItem[]
}
export interface ProductsResp {
  items: GroupItem[]
  top_by_revenue: GroupItem[]
  top_by_units: GroupItem[]
  top_by_profit: GroupItem[]
  lowest_by_revenue: GroupItem[]
}

export interface TrendPoint {
  period: string
  start: string
  revenue: number
  units: number
  orders: number
  profit: number | null
  moving_avg_3: number | null
  trend: number | null
  partial: boolean
}
export interface Seasonality {
  supported: boolean
  reason: string | null
  strength_r2: number | null
  message: string | null
  peak_months: string[]
  low_months: string[]
  months: { month: number; name: string; average_revenue: number | null; index: number | null }[]
  quarters: { quarter: string; average_revenue: number; share_pct: number }[]
  by_year: Record<string, (number | null)[]>
  years: { year: number; revenue: number; yoy_growth_pct: number | null }[]
}
export interface TrendsResp {
  granularity: Granularity
  series: TrendPoint[]
  trend: {
    months_analyzed?: number
    direction: string | null
    message: string
    annualized_growth_pct?: number | null
    last_12_vs_prior_12_pct?: number | null
  }
  seasonality: Seasonality
}

export interface HistoryPoint {
  period: string
  start: string
  revenue: number | null
}
export interface ForecastPoint {
  period: string
  start: string
  forecast: number
  lower: number
  upper: number
}
export interface ForecastSummary {
  months: number
  forecast_total: number
  trailing_12m_avg_monthly: number | null
  previous_period_total: number | null
  vs_previous_period_pct: number | null
  same_months_last_year_total: number | null
  vs_same_months_last_year_pct: number | null
  next_quarter_vs_previous_quarter_pct: number | null
  peak_month: { period: string; label: string; value: number }
  lowest_month: { period: string; label: string; value: number }
  avg_interval_width_pct: number | null
}
export interface ModelInfo {
  name: string
  description: string
  seasonality_detected: boolean
  seasonality_used: boolean
  seasonality_message: string | null
  training_months: number
  evaluated_on_months: number
}
export interface ForecastScope {
  is_filtered: boolean
  label: string
  filters: Record<string, string>
  description: string
}
export interface ForecastResp {
  scope: ForecastScope
  horizon_months: number
  interval_level_pct: number
  disclaimer: string
  notes: string[]
  history: HistoryPoint[]
  available: boolean
  message?: string
  forecast: ForecastPoint[]
  summary: ForecastSummary | null
  model: ModelInfo | null
  accuracy_headline?: { mape_pct: number | null; quality: string | null; verdict: string }
}

export type ModelKey = 'holt_winters' | 'naive' | 'seasonal_naive'
export interface Metrics {
  mae: number | null
  rmse: number | null
  mape_pct: number | null
}
export interface TestPoint {
  period: string
  actual: number | null
  holt_winters: number | null
  lower: number | null
  upper: number | null
  naive: number | null
  seasonal_naive: number | null
}
export interface Accuracy {
  available: boolean
  message?: string
  split?: {
    train_months: number
    test_months: number
    train_period: [string, string]
    test_period: [string, string]
    test_share_pct: number
  }
  metrics?: Record<ModelKey, Metrics>
  best_model?: ModelKey
  rmse_improvement_vs_naive_pct?: number | null
  interval_coverage_pct?: number
  interval_level_pct?: number
  quality?: string | null
  verdict?: string
  test_series?: TestPoint[]
  explanations?: Record<string, string>
  limitations?: string[]
}
export interface AccuracyResp {
  scope: ForecastScope
  available: boolean
  model: ModelInfo | null
  accuracy: Accuracy
}

export interface Inventory {
  high_demand_months: string[]
  low_demand_months: string[]
  threshold: string
  by_month: { period: string; forecast: number; vs_average_pct: number | null }[]
  note: string
}
export interface InsightsResp {
  scope: ForecastScope
  available: boolean
  message?: string
  key_insights: { type: 'historical' | 'diagnostic' | 'forecast'; text: string }[]
  forecast_insights: string[]
  recommendations: { text: string; basis: string }[]
  inventory: Inventory | null
  business_questions: Record<string, string>
  disclaimer?: string
}

export interface SalesRow {
  order_id: string
  order_date: string
  product: string
  category: string
  region: string
  quantity: number
  unit_price: number
  discount: number
  sales: number
}
export interface SalesPage {
  total: number
  page: number
  page_size: number
  items: SalesRow[]
}

export interface DataQualityReport {
  records_raw: number
  records_clean: number
  records_removed: number
  missing_values_total: number
  missing_values_by_column: Record<string, number>
  duplicate_orders: number
  invalid_dates: number
  discounts_recovered: number
  sales_formula_mismatches: number
  date_range: [string, string]
  transformations: string[]
}

type Params = Record<string, string | number | undefined>

function qs(p: Params): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== '') u.set(k, String(v))
  const s = u.toString()
  return s ? `?${s}` : ''
}

async function get<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}${qs(params)}`, { signal })
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return (await res.json()) as T
}

export const api = {
  filters: (s?: AbortSignal) => get<FilterOptions>('/filters', {}, s),
  dashboard: (f: Filters, s?: AbortSignal) => get<DashboardResp>('/dashboard', { ...f }, s),
  categories: (f: Filters, s?: AbortSignal) => get<GroupResp>('/categories', { ...f }, s),
  regions: (f: Filters, s?: AbortSignal) => get<GroupResp>('/regions', { ...f }, s),
  products: (f: Filters, s?: AbortSignal) => get<ProductsResp>('/products', { ...f, top_n: 5 }, s),
  trends: (f: Filters, granularity: Granularity, s?: AbortSignal) =>
    get<TrendsResp>('/trends', { ...f, granularity }, s),
  forecast: (f: Filters, horizon: Horizon, s?: AbortSignal) => get<ForecastResp>('/forecast', { ...f, horizon }, s),
  accuracy: (f: Filters, horizon: Horizon, s?: AbortSignal) =>
    get<AccuracyResp>('/forecast/accuracy', { ...f, horizon }, s),
  insights: (f: Filters, horizon: Horizon, s?: AbortSignal) => get<InsightsResp>('/insights', { ...f, horizon }, s),
  sales: (
    f: Filters,
    o: { q: string; sort_by: string; order: 'asc' | 'desc'; page: number; page_size: number },
    s?: AbortSignal,
  ) => get<SalesPage>('/sales', { ...f, ...o }, s),
  dataQuality: (s?: AbortSignal) => get<DataQualityReport>('/data-quality', {}, s),
}
