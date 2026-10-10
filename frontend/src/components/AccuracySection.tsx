import { useMemo } from 'react'
import { AccuracyChart } from '../charts/AccuracyChart'
import { testRows } from '../lib/chartData'
import { money, num, pct, periodLabel } from '../lib/format'
import type { AccuracyResp, ModelKey } from '../services/api'
import { ChartCard, Notice, Skeleton } from './ui'

const MODELS: { key: ModelKey; label: string }[] = [
  { key: 'holt_winters', label: 'Holt-Winters (the forecast model)' },
  { key: 'naive', label: 'Naive baseline' },
  { key: 'seasonal_naive', label: 'Seasonal-naive baseline' },
]

export function AccuracySection(props: { data: AccuracyResp | null; loading: boolean; error: string | null }) {
  const a = props.data?.accuracy
  const rows = useMemo(() => testRows(a?.test_series ?? []), [a])

  if (props.error && !props.data) return <Notice tone="error">{props.error}</Notice>
  if (!props.data || !a) return <Skeleton className="h-72" />
  if (!a.available || !a.metrics || !a.split) return <Notice tone="warn" title="No accuracy test">{a.message}</Notice>

  const m = a.metrics
  return (
    <div className={`space-y-4 ${props.loading ? 'opacity-60' : ''}`}>
      <Notice title="Result">
        {a.verdict} The model was trained on {a.split.train_months} months ({periodLabel(a.split.train_period[0])} to {periodLabel(a.split.train_period[1])}) and tested on the next {a.split.test_months} months ({periodLabel(a.split.test_period[0])} to {periodLabel(a.split.test_period[1])}), about {num(a.split.test_share_pct)}% of the history.
      </Notice>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="card lg:col-span-2">
          <h3 className="card-title">Forecast accuracy</h3>
          <p className="hint">Errors on the held-out months. Lower is better.</p>
          <table className="mt-3 w-full border-collapse text-left">
            <thead>
              <tr>
                <th className="th">Model</th>
                <th className="th text-right">MAE</th>
                <th className="th text-right">RMSE</th>
                <th className="th text-right">MAPE</th>
              </tr>
            </thead>
            <tbody>
              {MODELS.filter((x) => m[x.key]).map((x) => (
                <tr key={x.key}>
                  <td className="td">
                    {x.label}
                    {a.best_model === x.key && <span className="ml-2 rounded bg-ink px-1.5 py-0.5 text-xs text-surface">Lowest RMSE</span>}
                  </td>
                  <td className="td text-right tabular-nums">{money(m[x.key].mae)}</td>
                  <td className="td text-right tabular-nums">{money(m[x.key].rmse)}</td>
                  <td className="td text-right tabular-nums">{pct(m[x.key].mape_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-ink-2">Error vs naive baseline (RMSE)</dt>
              <dd className="tabular-nums">
                {a.rmse_improvement_vs_naive_pct == null
                  ? '-'
                  : a.rmse_improvement_vs_naive_pct >= 0
                    ? `${pct(a.rmse_improvement_vs_naive_pct, 0)} lower`
                    : `${pct(-a.rmse_improvement_vs_naive_pct, 0)} higher`}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-2">Months inside the {a.interval_level_pct}% interval</dt>
              <dd className="tabular-nums">{pct(a.interval_coverage_pct, 0)}</dd>
            </div>
          </dl>
        </div>

        <ChartCard
          className="lg:col-span-3"
          title="Held-out months: actual vs predicted"
          subtitle="Each model predicted these months without seeing them."
          legend={[
            { label: 'Actual', color: 'var(--s1)' },
            { label: 'Holt-Winters', color: 'var(--s2)' },
            { label: 'Naive', color: 'var(--muted)', dashed: true },
            { label: 'Seasonal naive', color: 'var(--s3)', dashed: true },
          ]}
          table={{
            columns: ['Month', 'Actual', 'Holt-Winters', 'Naive', 'Seasonal naive'],
            rows: rows.map((r) => [periodLabel(r.period), money(r.actual), money(r.holt_winters), money(r.naive), money(r.seasonal_naive)]),
          }}
        >
          <AccuracyChart rows={rows} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <details className="card">
          <summary className="card-title cursor-pointer">What these measures mean</summary>
          <dl className="mt-3 space-y-2 text-sm">
            {(['mae', 'rmse', 'mape', 'naive', 'seasonal_naive', 'interval_coverage'] as const).map((k) =>
              a.explanations?.[k] ? (
                <div key={k}>
                  <dd>{a.explanations[k]}</dd>
                </div>
              ) : null,
            )}
          </dl>
        </details>
        <div className="card">
          <h3 className="card-title">Limitations</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
            {a.limitations?.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
