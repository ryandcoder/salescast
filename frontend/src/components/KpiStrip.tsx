import { money, money2, num, pct, periodLabel } from '../lib/format'
import type { Kpis } from '../services/api'

function Cell(props: { label: string; value: string; sub?: string; loading: boolean }) {
  return (
    <div className="min-w-0 bg-surface p-4">
      <div className="text-sm text-ink-2">{props.label}</div>
      <div className={`mt-1 truncate text-2xl font-semibold tracking-tight ${props.loading ? 'opacity-50' : ''}`}>{props.value}</div>
      {props.sub && <div className="mt-0.5 truncate text-xs text-ink-2">{props.sub}</div>}
    </div>
  )
}

/** The headline figures as one ruled strip (not a row of separate cards). Everything comes from /api/dashboard. */
export function KpiStrip({ kpis, loading }: { kpis: Kpis | null; loading: boolean }) {
  const k = kpis
  const range = k?.data_range[0] && k.data_range[1] ? `${periodLabel(k.data_range[0].slice(0, 7))} to ${periodLabel(k.data_range[1].slice(0, 7))}` : undefined
  const bestProduct = k?.best_product_by_revenue
  const mostUnits = k?.best_product_by_units
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-edge bg-edge md:grid-cols-4">
      <Cell loading={loading} label="Total revenue" value={money(k?.total_revenue)} sub={range} />
      <Cell loading={loading} label="Total orders" value={num(k?.total_orders)} />
      <Cell loading={loading} label="Units sold" value={num(k?.units_sold)} />
      <Cell loading={loading} label="Average order value" value={money2(k?.average_order_value)} />
      <Cell loading={loading} label="Average monthly revenue" value={money(k?.average_monthly_revenue)} sub={k ? `${k.months_covered} months` : undefined} />
      <Cell
        loading={loading}
        label="Best-selling product"
        value={bestProduct?.name ?? '-'}
        sub={
          bestProduct
            ? `${money(bestProduct.revenue)} revenue${mostUnits && mostUnits.name !== bestProduct.name ? `. Most units: ${mostUnits.name} (${num(mostUnits.units)})` : ''}`
            : undefined
        }
      />
      <Cell loading={loading} label="Best-performing region" value={k?.best_region?.name ?? '-'} sub={k?.best_region ? `${money(k.best_region.revenue)} from ${num(k.best_region.orders)} orders` : undefined} />
      {k?.profit ? (
        <Cell loading={loading} label="Total profit" value={money(k.profit.total_profit)} sub={`${pct(k.profit.profit_margin_pct)} margin`} />
      ) : (
        <Cell loading={loading} label="Profit" value="Not in dataset" />
      )}
    </div>
  )
}
