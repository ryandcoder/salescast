import { useMemo, useState } from 'react'
import { money, money2, num, pct } from '../lib/format'
import type { GroupItem, ProductsResp } from '../services/api'
import { EmptyState, Notice, RankBars } from './ui'

type SortKey = 'name' | 'category' | 'revenue' | 'units' | 'avg_price' | 'orders' | 'profit_margin_pct'

const COLUMNS: { key: SortKey; label: string; numeric: boolean; cell: (p: GroupItem) => string }[] = [
  { key: 'name', label: 'Product', numeric: false, cell: (p) => p.name },
  { key: 'category', label: 'Category', numeric: false, cell: (p) => p.category ?? '-' },
  { key: 'revenue', label: 'Revenue', numeric: true, cell: (p) => money(p.revenue) },
  { key: 'units', label: 'Units sold', numeric: true, cell: (p) => num(p.units) },
  { key: 'avg_price', label: 'Average price', numeric: true, cell: (p) => money2(p.avg_price) },
  { key: 'orders', label: 'Orders', numeric: true, cell: (p) => num(p.orders) },
  { key: 'profit_margin_pct', label: 'Profit margin', numeric: true, cell: (p) => pct(p.profit_margin_pct) },
]

export function ProductsSection({ data, loading }: { data: ProductsResp | null; loading: boolean }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'revenue', dir: 'desc' })
  const [showAll, setShowAll] = useState(false)

  const hasProfit = !!data?.items.some((p) => p.profit_margin_pct !== null)
  const columns = COLUMNS.filter((c) => c.key !== 'profit_margin_pct' || hasProfit)

  const sorted = useMemo(() => {
    const items = [...(data?.items ?? [])]
    const { key, dir } = sort
    items.sort((a, b) => {
      const x = a[key] ?? null
      const y = b[key] ?? null
      if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1 // missing values always last
      const c = typeof x === 'string' ? x.localeCompare(String(y)) : Number(x) - Number(y)
      return dir === 'asc' ? c : -c
    })
    return items
  }, [data, sort])

  if (!data) return <div className="card"><EmptyState>{loading ? 'Loading products...' : 'No product data.'}</EmptyState></div>
  const rows = showAll ? sorted : sorted.slice(0, 10)

  const list = (items: GroupItem[], value: (p: GroupItem) => { n: number; label: string }) =>
    items.map((p) => ({ name: p.name, value: value(p).n, label: value(p).label, sub: p.category }))

  return (
    <div className="space-y-4">
      <Notice>
        Selling the most units is not the same as earning the most revenue. Compare the rankings below before drawing conclusions.
      </Notice>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card">
          <h3 className="card-title">Top products by revenue</h3>
          <div className="mt-3"><RankBars items={list(data.top_by_revenue, (p) => ({ n: p.revenue, label: money(p.revenue) }))} /></div>
        </div>
        <div className="card">
          <h3 className="card-title">Top products by units sold</h3>
          <div className="mt-3"><RankBars color="var(--s3)" items={list(data.top_by_units, (p) => ({ n: p.units, label: `${num(p.units)} units` }))} /></div>
        </div>
        <div className="card">
          <h3 className="card-title">Lowest-performing products</h3>
          <p className="hint">Lowest revenue in the current selection.</p>
          <div className="mt-3"><RankBars color="var(--muted)" items={list(data.lowest_by_revenue, (p) => ({ n: p.revenue, label: money(p.revenue) }))} /></div>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">All products</h3>
        <p className="hint">Select a column heading to sort.</p>
        <div className={`mt-3 overflow-x-auto ${loading ? 'opacity-60' : ''}`}>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                {columns.map((c) => {
                  const active = sort.key === c.key
                  return (
                    <th key={c.key} className={`th ${c.numeric ? 'text-right' : ''}`} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-s1"
                        onClick={() => setSort({ key: c.key, dir: active && sort.dir === 'desc' ? 'asc' : 'desc' })}
                      >
                        {c.label}
                        <span aria-hidden="true">{active ? (sort.dir === 'asc' ? '▲' : '▼') : ''}</span>
                      </button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.name}>
                  {columns.map((c) => (
                    <td key={c.key} className={`td ${c.numeric ? 'text-right tabular-nums' : ''}`}>
                      {c.cell(p)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sorted.length > 10 && (
          <button type="button" className="btn mt-3" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show top 10' : `Show all ${sorted.length} products`}
          </button>
        )}
      </div>
    </div>
  )
}
