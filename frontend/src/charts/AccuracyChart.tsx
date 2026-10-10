import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '../components/ui'
import { axisLabel, compactMoney, money, periodLabel } from '../lib/format'
import type { TestPoint } from '../services/api'
import { RowTooltip, TICK } from './RowTooltip'

/** Held-out months: what actually happened versus each model's prediction for the same months. */
export function AccuracyChart({ rows }: { rows: TestPoint[] }) {
  if (rows.length === 0) return <EmptyState />
  return (
    <div className="h-72 w-full" role="img" aria-label="Held-out months: actual revenue versus model predictions. Use Show table for the values.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="period" tickFormatter={axisLabel} tick={TICK} stroke="var(--axis)" tickLine={false} minTickGap={20} />
          <YAxis tickFormatter={compactMoney} tick={TICK} axisLine={false} tickLine={false} width={56} domain={[0, 'auto']} />
          <Tooltip
            cursor={{ stroke: 'var(--axis)' }}
            content={
              <RowTooltip<TestPoint>
                render={(r) => (
                  <>
                    <div className="font-semibold">{periodLabel(r.period)}</div>
                    <div>Actual: {money(r.actual)}</div>
                    <div>Holt-Winters: {money(r.holt_winters)}</div>
                    <div>Naive: {money(r.naive)}</div>
                    {r.seasonal_naive !== null && <div>Seasonal naive: {money(r.seasonal_naive)}</div>}
                  </>
                )}
              />
            }
          />
          <Line dataKey="naive" name="Naive" stroke="var(--muted)" strokeWidth={2} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
          <Line dataKey="seasonal_naive" name="Seasonal naive" stroke="var(--s3)" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
          <Line dataKey="holt_winters" name="Holt-Winters" stroke="var(--s2)" strokeWidth={2} dot={{ r: 4, fill: 'var(--s2)', stroke: 'var(--surface)', strokeWidth: 2 }} isAnimationActive={false} />
          <Line dataKey="actual" name="Actual" stroke="var(--s1)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
