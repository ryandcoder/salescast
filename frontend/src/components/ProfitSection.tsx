import { money, num, pct } from '../lib/format'
import type { GroupItem } from '../services/api'
import { RankBars } from './ui'

function profitBars(items: GroupItem[]) {
  return items
    .filter((i) => i.profit !== null)
    .sort((a, b) => (b.profit ?? 0) - (a.profit ?? 0))
    .map((i) => ({ name: i.name, value: i.profit ?? 0, label: money(i.profit), sub: `${pct(i.profit_margin_pct)} margin on ${money(i.revenue)} revenue` }))
}

/** Rendered only when the dataset has profit values; the API sends profit as null otherwise. */
export function ProfitSection(props: { categories: GroupItem[]; regions: GroupItem[]; products: GroupItem[] }) {
  const products = profitBars(props.products)
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="card">
        <h3 className="card-title">Profit by category</h3>
        <div className="mt-3"><RankBars color="var(--s3)" items={profitBars(props.categories)} /></div>
      </div>
      <div className="card">
        <h3 className="card-title">Profit by region</h3>
        <div className="mt-3"><RankBars color="var(--s3)" items={profitBars(props.regions)} /></div>
      </div>
      <div className="card">
        <h3 className="card-title">Profit by product</h3>
        <p className="hint">Top 8 of {num(products.length)}.</p>
        <div className="mt-3"><RankBars color="var(--s3)" items={products.slice(0, 8)} /></div>
      </div>
    </div>
  )
}
