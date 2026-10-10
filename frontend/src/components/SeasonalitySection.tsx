import { SeasonalChart, YEAR_COLORS, seasonalYears } from '../charts/SeasonalChart'
import { MONTHS, compactMoney, money, num, pct, signedPct } from '../lib/format'
import type { TrendsResp } from '../services/api'
import { ChartCard, EmptyState, Notice } from './ui'

/** Average revenue per calendar month as plain HTML columns, with the value printed on every column. */
function MonthColumns({ months }: { months: TrendsResp['seasonality']['months'] }) {
  const max = Math.max(0, ...months.map((m) => m.average_revenue ?? 0)) || 1
  return (
    <ul className="flex h-56 items-end gap-1.5 sm:gap-2">
      {months.map((m) => (
        <li key={m.name} className="flex h-full min-w-0 flex-1 flex-col justify-end text-center" title={m.index !== null ? `${m.name}: ${m.index.toFixed(2)}x a typical month` : m.name}>
          <span className="mb-1 truncate text-[10px] tabular-nums text-ink-2 sm:text-xs">{m.average_revenue !== null ? compactMoney(m.average_revenue) : '-'}</span>
          <div className="rounded-t-[4px]" style={{ height: `${((m.average_revenue ?? 0) / max) * 80}%`, background: 'var(--s1)' }} />
          <span className="mt-1 text-xs text-ink-2">{m.name}</span>
        </li>
      ))}
    </ul>
  )
}

export function SeasonalitySection({ data, loading }: { data: TrendsResp | null; loading: boolean }) {
  if (!data) return <div className="card"><EmptyState>{loading ? 'Loading...' : 'No data.'}</EmptyState></div>
  const s = data.seasonality
  const years = seasonalYears(s.by_year)

  return (
    <div className="space-y-4">
      <Notice tone={s.supported ? 'info' : 'warn'} title={s.supported ? 'Seasonal pattern found' : 'No seasonal pattern claimed'}>
        {s.message ?? 'Not enough data.'}
      </Notice>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Average revenue by month"
          subtitle="Complete months only, averaged across years."
          table={{ columns: ['Month', 'Average revenue', 'Index vs a typical month'], rows: s.months.map((m) => [m.name, money(m.average_revenue), m.index !== null ? `${m.index.toFixed(2)}x` : '-']) }}
          busy={loading}
        >
          <MonthColumns months={s.months} />
        </ChartCard>

        <ChartCard
          title="Each year, month by month"
          subtitle={s.supported ? 'A recurring shape across the lines is what seasonality looks like.' : 'Shown for inspection only; the data does not support a seasonal claim.'}
          legend={years.map((y, i) => ({ label: y, color: YEAR_COLORS[i] }))}
          table={{
            columns: ['Month', ...years],
            rows: MONTHS.map((m, i) => [m, ...years.map((y) => money(s.by_year[y]?.[i] ?? null))]),
          }}
          busy={loading}
        >
          <SeasonalChart byYear={s.by_year} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="card-title">Quarters</h3>
          <p className="hint">Average revenue per quarter and its share of the year.</p>
          {s.quarters.length === 0 ? (
            <EmptyState>No complete quarters in the current selection.</EmptyState>
          ) : (
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {s.quarters.map((q) => (
                <div key={q.quarter}>
                  <dt className="text-sm text-ink-2">{q.quarter}</dt>
                  <dd className="text-lg font-semibold tabular-nums">{money(q.average_revenue)}</dd>
                  <dd className="text-xs text-ink-2">{pct(q.share_pct)} of the year</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <div className="card">
          <h3 className="card-title">Years</h3>
          <p className="hint">Full calendar years only.</p>
          {s.years.length === 0 ? (
            <EmptyState>No complete years in the current selection.</EmptyState>
          ) : (
            <table className="mt-3 w-full border-collapse text-left">
              <thead>
                <tr>
                  <th className="th">Year</th>
                  <th className="th text-right">Revenue</th>
                  <th className="th text-right">Change vs previous year</th>
                </tr>
              </thead>
              <tbody>
                {s.years.map((y) => (
                  <tr key={y.year}>
                    <td className="td">{y.year}</td>
                    <td className="td text-right tabular-nums">{money(y.revenue)}</td>
                    <td className="td text-right tabular-nums">{y.yoy_growth_pct === null ? '-' : signedPct(y.yoy_growth_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <p className="hint">{num(data.trend.months_analyzed ?? 0)} complete months were used for the trend and seasonality analysis.</p>
    </div>
  )
}
