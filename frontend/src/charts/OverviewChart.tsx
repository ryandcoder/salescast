import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '../components/ui'
import type { OverviewRow } from '../lib/chartData'
import { axisLabel, periodLabel } from '../lib/format'
import { RowTooltip, TICK } from './RowTooltip'

export function OverviewChart(props: {
  rows: OverviewRow[]
  label: string
  format: (n: number | null) => string
  formatAxis: (n: number) => string
  showMovingAvg: boolean
  showTrend: boolean
}) {
  if (props.rows.length === 0) return <EmptyState />
  return (
    <div className="h-72 w-full sm:h-80" role="img" aria-label={`${props.label} over time, line chart. Use Show table for the values.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={props.rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="period" tickFormatter={axisLabel} tick={TICK} stroke="var(--axis)" tickLine={false} minTickGap={28} />
          <YAxis tickFormatter={props.formatAxis} tick={TICK} axisLine={false} tickLine={false} width={56} domain={[0, 'auto']} />
          <Tooltip
            cursor={{ stroke: 'var(--axis)' }}
            content={
              <RowTooltip<OverviewRow>
                render={(r) => (
                  <>
                    <div className="font-semibold">
                      {periodLabel(r.period)}
                      {r.partial ? ' (partial period)' : ''}
                    </div>
                    <div>
                      {props.label}: {props.format(r.value)}
                    </div>
                    {r.movingAvg !== null && <div>3-month average: {props.format(r.movingAvg)}</div>}
                    {r.trend !== null && <div>Trend line: {props.format(r.trend)}</div>}
                  </>
                )}
              />
            }
          />
          {props.showTrend && (
            <Line dataKey="trend" name="Trend line" stroke="var(--ink-2)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
          )}
          {props.showMovingAvg && (
            <Line dataKey="movingAvg" name="3-month moving average" stroke="var(--s2)" strokeWidth={2} dot={false} isAnimationActive={false} />
          )}
          <Line dataKey="value" name={props.label} stroke="var(--s1)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
