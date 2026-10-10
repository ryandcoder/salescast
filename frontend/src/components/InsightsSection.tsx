import { money, periodLabel, signedPct } from '../lib/format'
import type { InsightsResp } from '../services/api'
import { Notice, Skeleton } from './ui'

const GROUPS: { type: 'historical' | 'diagnostic' | 'forecast'; title: string }[] = [
  { type: 'historical', title: 'What happened' },
  { type: 'diagnostic', title: 'What drove the change' },
  { type: 'forecast', title: "What's likely next" },
]

const QUESTIONS: { key: string; label: string }[] = [
  { key: 'what_happened', label: 'What happened?' },
  { key: 'what_contributed', label: 'What contributed to the change?' },
  { key: 'what_is_likely', label: 'What is likely to happen next?' },
  { key: 'should_inventory_increase', label: 'Should inventory increase?' },
  { key: 'categories_expected_to_grow', label: 'Which categories may grow?' },
  { key: 'months_with_lower_demand', label: 'Which months may have lower demand?' },
  { key: 'upcoming_seasonal_peaks', label: 'Are there upcoming seasonal peaks?' },
]

export function InsightsSection(props: { data: InsightsResp | null; loading: boolean; error: string | null }) {
  const d = props.data
  if (props.error && !d) return <Notice tone="error">{props.error}</Notice>
  if (!d) return <Skeleton className="h-72" />
  if (!d.available) return <Notice tone="warn" title="No insights">{d.message}</Notice>
  const inv = d.inventory

  return (
    <div className={`space-y-4 ${props.loading ? 'opacity-60' : ''}`}>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card" id="key-insights">
          <h3 className="card-title">Key insights</h3>
          <p className="hint">Written from the numbers in the current selection, not fixed text.</p>
          {GROUPS.map((g) => {
            const items = d.key_insights.filter((i) => i.type === g.type)
            if (items.length === 0) return null
            return (
              <div key={g.type} className="mt-4">
                <h4 className="text-sm font-semibold">{g.title}</h4>
                <ul className="mt-1 list-disc space-y-1.5 pl-5 text-sm">
                  {items.map((i) => (
                    <li key={i.text}>{i.text}</li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>

        <div className="space-y-4">
          <div className="card" id="recommendations">
            <h3 className="card-title">Business recommendations</h3>
            <p className="hint">Each one says what it is based on.</p>
            <ul className="mt-3 space-y-3 text-sm">
              {d.recommendations.map((r) => (
                <li key={r.text}>
                  <div>{r.text}</div>
                  {r.basis && <div className="mt-0.5 text-xs text-ink-2">Based on: {r.basis}</div>}
                </li>
              ))}
            </ul>
          </div>

          <div className="card" id="inventory">
            <h3 className="card-title">Inventory planning</h3>
            {!inv ? (
              <p className="hint mt-1">No forecast is available for this selection, so there is no inventory signal.</p>
            ) : (
              <>
                <dl className="mt-3 space-y-2 text-sm">
                  <div>
                    <dt className="font-semibold">Expected higher demand</dt>
                    <dd>{inv.high_demand_months.length ? inv.high_demand_months.join(', ') : 'None in the forecast window'}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold">Expected lower demand</dt>
                    <dd>{inv.low_demand_months.length ? inv.low_demand_months.join(', ') : 'None in the forecast window'}</dd>
                  </div>
                </dl>
                <table className="mt-3 w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <th className="th">Month</th>
                      <th className="th text-right">Forecast revenue</th>
                      <th className="th text-right">vs recent monthly average</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inv.by_month.map((m) => (
                      <tr key={m.period}>
                        <td className="td">{periodLabel(m.period)}</td>
                        <td className="td text-right tabular-nums">{money(m.forecast)}</td>
                        <td className="td text-right tabular-nums">{signedPct(m.vs_average_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-ink-2">{inv.threshold}</p>
                <p className="mt-1 text-xs text-ink-2">{inv.note}</p>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">Business questions</h3>
        <dl className="mt-3 grid gap-x-8 gap-y-3 text-sm md:grid-cols-2">
          {QUESTIONS.map((q) =>
            d.business_questions[q.key] ? (
              <div key={q.key}>
                <dt className="font-semibold">{q.label}</dt>
                <dd className="mt-0.5 text-ink-2">{d.business_questions[q.key]}</dd>
              </div>
            ) : null,
          )}
        </dl>
      </div>
    </div>
  )
}
