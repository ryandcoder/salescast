import { useMemo } from 'react'
import { ForecastChart } from '../charts/ForecastChart'
import { buildForecastRows } from '../lib/chartData'
import { money, pct, periodLabel, signedPct } from '../lib/format'
import type { ForecastResp } from '../services/api'
import { ChartCard, Notice, Skeleton } from './ui'

function Stat(props: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 bg-surface p-4">
      <div className="text-sm text-ink-2">{props.label}</div>
      <div className="mt-1 truncate text-xl font-semibold tracking-tight">{props.value}</div>
      {props.sub && <div className="mt-0.5 text-xs text-ink-2">{props.sub}</div>}
    </div>
  )
}

export function ForecastSection(props: { data: ForecastResp | null; loading: boolean; error: string | null }) {
  const { data } = props
  const rows = useMemo(() => (data?.available ? buildForecastRows(data.history, data.forecast) : []), [data])

  if (props.error && !data) return <Notice tone="error">{props.error}</Notice>
  if (!data) return <Skeleton className="h-96" />

  const s = data.summary
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="rounded-md bg-ink px-2 py-1 text-sm font-semibold text-surface">{data.scope.label}</span>
        <span className="hint">{data.scope.description}</span>
      </div>

      {!data.available ? (
        <Notice tone="warn" title="No forecast for this selection">{data.message}</Notice>
      ) : (
        <>
          <ChartCard
            title={`Monthly revenue: history and next ${data.horizon_months} months`}
            subtitle={`The shaded band is the ${data.interval_level_pct}% prediction interval: about ${100 - data.interval_level_pct}% of months would be expected to land outside it.`}
            legend={[
              { label: 'Actual', color: 'var(--s1)' },
              { label: 'Forecast', color: 'var(--s2)', dashed: true },
              { label: `${data.interval_level_pct}% prediction interval`, color: 'var(--s2)', box: true },
            ]}
            table={{
              columns: ['Month', 'Type', 'Revenue', 'Lower bound', 'Upper bound'],
              rows: rows.map((r) => [periodLabel(r.period), r.isForecast ? 'Forecast' : 'Actual', money(r.isForecast ? r.forecast : r.actual), r.isForecast ? money(r.lower) : '-', r.isForecast ? money(r.upper) : '-']),
            }}
            busy={props.loading}
          >
            <ForecastChart rows={rows} intervalPct={data.interval_level_pct} />
          </ChartCard>

          {s && (
            <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-edge bg-edge md:grid-cols-4 ${props.loading ? 'opacity-60' : ''}`}>
              <Stat label={`Expected revenue, next ${s.months} months`} value={money(s.forecast_total)} sub={s.vs_same_months_last_year_pct !== null ? `${signedPct(s.vs_same_months_last_year_pct)} vs the same months last year` : undefined} />
              <Stat label="Next quarter vs last quarter" value={signedPct(s.next_quarter_vs_previous_quarter_pct)} sub="Forecast vs the last 3 actual months" />
              <Stat label="Strongest forecast month" value={s.peak_month.label} sub={money(s.peak_month.value)} />
              <Stat label="Weakest forecast month" value={s.lowest_month.label} sub={money(s.lowest_month.value)} />
            </div>
          )}

          {data.model && (
            <div className="card text-sm">
              <p>
                <span className="font-semibold">Model:</span> {data.model.description}. Trained on {data.model.training_months} complete months; its accuracy was measured on the last {data.model.evaluated_on_months} months, which it had not seen.
              </p>
              {data.model.seasonality_message && <p className="mt-1 text-ink-2">{data.model.seasonality_message}</p>}
              {s?.avg_interval_width_pct != null && <p className="mt-1 text-ink-2">The prediction interval is on average {pct(s.avg_interval_width_pct, 0)} of the forecast value wide.</p>}
              {data.accuracy_headline && (
                <p className="mt-1">
                  Average error on held-out months: {pct(data.accuracy_headline.mape_pct)}
                  {data.accuracy_headline.quality ? ` (${data.accuracy_headline.quality})` : ''}. <a className="underline" href="#accuracy">See the accuracy details</a>.
                </p>
              )}
              {data.notes.length > 0 && (
                <ul className="mt-2 list-disc space-y-0.5 pl-5 text-ink-2">
                  {data.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
      <Notice>{data.disclaimer}</Notice>
    </div>
  )
}
