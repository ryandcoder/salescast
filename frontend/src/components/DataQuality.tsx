import { useApi } from '../hooks/useApi'
import { num, periodLabel } from '../lib/format'
import { api } from '../services/api'

/** The cleaning summary written when the dataset was loaded (GET /api/data-quality). */
export function DataQuality() {
  const { data, error } = useApi((s) => api.dataQuality(s), 'dq')
  if (error) return <p className="hint">The data-quality report is not available: {error}</p>
  if (!data) return <p className="hint">Loading the data-quality summary...</p>

  const rows: [string, string][] = [
    ['Records in the source file', num(data.records_raw)],
    ['Records after cleaning', num(data.records_clean)],
    ['Missing values', num(data.missing_values_total)],
    ['Duplicate orders removed', num(data.duplicate_orders)],
    ['Invalid dates', num(data.invalid_dates)],
    ['Discounts recovered from sales and price', num(data.discounts_recovered)],
    ['Sales that do not match quantity x price x (1 - discount)', num(data.sales_formula_mismatches)],
    ['Date range', `${periodLabel(data.date_range[0].slice(0, 7))} to ${periodLabel(data.date_range[1].slice(0, 7))}`],
  ]
  return (
    <div className="card">
      <dl className="grid gap-x-8 gap-y-2 text-sm md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-edge py-1">
            <dt className="text-ink-2">{k}</dt>
            <dd className="font-medium tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
      <h3 className="card-title mt-4">Transformations applied</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
        {data.transformations.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </div>
  )
}
