import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { money2, num } from '../lib/format'
import { api, type Filters } from '../services/api'
import { Notice } from './ui'

const PAGE_SIZE = 25

const COLUMNS: { key: string; label: string; numeric: boolean }[] = [
  { key: 'order_id', label: 'Order ID', numeric: false },
  { key: 'order_date', label: 'Order date', numeric: false },
  { key: 'product', label: 'Product', numeric: false },
  { key: 'category', label: 'Category', numeric: false },
  { key: 'region', label: 'Region', numeric: false },
  { key: 'quantity', label: 'Quantity', numeric: true },
  { key: 'unit_price', label: 'Unit price', numeric: true },
  { key: 'discount', label: 'Discount', numeric: true },
  { key: 'sales', label: 'Sales', numeric: true },
]

/** Search, sort and pagination all run in the API (SQL), so the table stays fast on large datasets. */
export function SalesTable({ filters }: { filters: Filters }) {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' }>({ key: 'order_date', dir: 'desc' })
  const [pg, setPg] = useState({ page: 1, scope: '' })

  useEffect(() => {
    const t = setTimeout(() => setQ(input.trim()), 300)
    return () => clearTimeout(t)
  }, [input])

  // Any change to filters, search or sort starts again at page 1 (derived, so no extra request fires).
  const scope = JSON.stringify([filters, q, sort])
  const page = pg.scope === scope ? pg.page : 1
  const { data, error, loading } = useApi(
    (s) => api.sales(filters, { q, sort_by: sort.key, order: sort.dir, page, page_size: PAGE_SIZE }, s),
    `${scope}|${page}`,
  )

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const goto = (n: number) => setPg({ page: Math.min(Math.max(1, n), pages), scope })

  return (
    <div className="card">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink-2">
          Search orders, products, categories or regions
          <input type="search" className="field w-72 max-w-full" value={input} onChange={(e) => setInput(e.target.value)} placeholder="For example: laptop" />
        </label>
        <p className="text-sm text-ink-2" aria-live="polite">
          {data ? `${num(data.total)} orders` : 'Loading...'}
        </p>
      </div>

      {error && <div className="mt-3"><Notice tone="error">{error}</Notice></div>}

      <div className={`mt-3 overflow-x-auto ${loading ? 'opacity-60' : ''}`}>
        <table className="w-full border-collapse text-left">
          <thead>
            <tr>
              {COLUMNS.map((c) => {
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
            {data?.items.map((r) => (
              <tr key={r.order_id}>
                <td className="td tabular-nums">{r.order_id}</td>
                <td className="td tabular-nums whitespace-nowrap">{r.order_date}</td>
                <td className="td">{r.product}</td>
                <td className="td">{r.category}</td>
                <td className="td">{r.region}</td>
                <td className="td text-right tabular-nums">{num(r.quantity)}</td>
                <td className="td text-right tabular-nums">{money2(r.unit_price)}</td>
                <td className="td text-right tabular-nums">{Math.round(r.discount * 100)}%</td>
                <td className="td text-right tabular-nums">{money2(r.sales)}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td className="td text-center text-ink-2" colSpan={COLUMNS.length}>
                  No orders match the current filters and search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
        <span className="text-ink-2">
          Page {num(page)} of {num(pages)}
        </span>
        <div className="flex gap-2">
          <button type="button" className="btn" disabled={page <= 1} onClick={() => goto(1)}>First</button>
          <button type="button" className="btn" disabled={page <= 1} onClick={() => goto(page - 1)}>Previous</button>
          <button type="button" className="btn" disabled={page >= pages} onClick={() => goto(page + 1)}>Next</button>
          <button type="button" className="btn" disabled={page >= pages} onClick={() => goto(pages)}>Last</button>
        </div>
      </div>
    </div>
  )
}
