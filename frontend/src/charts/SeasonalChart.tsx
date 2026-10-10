import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '../components/ui'
import { buildSeasonalRows } from '../lib/chartData'
import { compactMoney, money } from '../lib/format'
import { TICK } from './RowTooltip'

// One colour per year, in year order (latest four years), so a year keeps its colour across filters.
export const YEAR_COLORS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)']

export function seasonalYears(byYear: Record<string, (number | null)[]>): string[] {
  return buildSeasonalRows(byYear, YEAR_COLORS.length).years
}

/** Each year as its own line across Jan-Dec, so a recurring yearly shape is easy to see (or not). */
export function SeasonalChart({ byYear }: { byYear: Record<string, (number | null)[]> }) {
  const { years, rows } = buildSeasonalRows(byYear, YEAR_COLORS.length)
  if (years.length === 0) return <EmptyState>No complete months for the current filters.</EmptyState>
  return (
    <div className="h-72 w-full" role="img" aria-label="Revenue by calendar month, one line per year. Use Show table for the values.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="month" tick={TICK} stroke="var(--axis)" tickLine={false} />
          <YAxis tickFormatter={compactMoney} tick={TICK} axisLine={false} tickLine={false} width={56} domain={[0, 'auto']} />
          <Tooltip
            cursor={{ stroke: 'var(--axis)' }}
            content={({ active, payload, label }) =>
              active && payload && payload.length ? (
                <div className="rounded-lg border border-edge bg-surface px-3 py-2 text-xs text-ink shadow-lg">
                  <div className="font-semibold">{label}</div>
                  {payload.map((p) => (
                    <div key={String(p.dataKey)}>
                      {String(p.dataKey)}: {money(typeof p.value === 'number' ? p.value : null)}
                    </div>
                  ))}
                </div>
              ) : null
            }
          />
          {years.map((y, i) => (
            <Line key={y} dataKey={y} name={y} stroke={YEAR_COLORS[i]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
