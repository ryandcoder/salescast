import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '../components/ui'
import { firstForecastPeriod, lastActualPeriod, type ForecastRow } from '../lib/chartData'
import { axisLabel, compactMoney, money, periodLabel } from '../lib/format'
import { RowTooltip, TICK } from './RowTooltip'

/**
 * Actual revenue (solid blue) then forecast (dashed orange with markers) inside a shaded "future" zone.
 * The prediction interval is a stacked pair of areas: an invisible one up to the lower bound,
 * then a tinted one whose height is (upper - lower).
 */
export function ForecastChart(props: { rows: ForecastRow[]; intervalPct: number }) {
  const first = firstForecastPeriod(props.rows)
  const last = lastActualPeriod(props.rows)
  if (props.rows.length === 0 || !first) return <EmptyState />
  const end = props.rows[props.rows.length - 1].period
  return (
    <div
      className="h-80 w-full sm:h-96"
      role="img"
      aria-label="Monthly revenue: solid line is actual history, dashed line is the forecast with a shaded prediction interval. Use Show table for the values."
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={props.rows} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="period" tickFormatter={axisLabel} tick={TICK} stroke="var(--axis)" tickLine={false} minTickGap={28} />
          <YAxis tickFormatter={compactMoney} tick={TICK} axisLine={false} tickLine={false} width={56} domain={[0, 'auto']} />
          <ReferenceArea x1={first} x2={end} fill="var(--s2)" fillOpacity={0.06} stroke="none" />
          {last && (
            <ReferenceLine
              x={last}
              stroke="var(--axis)"
              strokeDasharray="4 4"
              label={{ value: 'Forecast starts', position: 'insideTopRight', fill: 'var(--ink-2)', fontSize: 12 }}
            />
          )}
          <Tooltip
            cursor={{ stroke: 'var(--axis)' }}
            content={
              <RowTooltip<ForecastRow>
                render={(r) => (
                  <>
                    <div className="font-semibold">{periodLabel(r.period)}</div>
                    {r.isForecast ? (
                      <>
                        <div>Forecast: {money(r.forecast)}</div>
                        <div>
                          {props.intervalPct}% range: {money(r.lower)} to {money(r.upper)}
                        </div>
                      </>
                    ) : (
                      <div>Actual: {money(r.actual)}</div>
                    )}
                  </>
                )}
              />
            }
          />
          <Area dataKey="lower" stackId="interval" stroke="none" fill="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band" stackId="interval" stroke="none" fill="var(--s2)" fillOpacity={0.2} isAnimationActive={false} legendType="none" />
          <Line dataKey="actual" name="Actual" stroke="var(--s1)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          <Line
            dataKey="forecast"
            name="Forecast"
            stroke="var(--s2)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={{ r: 4, fill: 'var(--s2)', stroke: 'var(--surface)', strokeWidth: 2 }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
