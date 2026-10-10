import { EMPTY_FILTERS, isFiltered, type FilterOptions, type Filters } from '../services/api'

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-ink-2">
      {props.label}
      {props.children}
    </label>
  )
}

export function FilterBar(props: { options: FilterOptions | null; filters: Filters; onChange: (f: Filters) => void }) {
  const { options, filters } = props

  const set = (patch: Partial<Filters>) => {
    const next = { ...filters, ...patch }
    // A product belongs to one category: drop a product that no longer matches the chosen category.
    if (patch.category !== undefined && next.product && next.category) {
      const p = options?.products.find((x) => x.product === next.product)
      if (p && p.category !== next.category) next.product = ''
    }
    // Keep the date range ordered.
    if (next.date_from && next.date_to && next.date_from > next.date_to) {
      if (patch.date_from !== undefined) next.date_to = next.date_from
      else next.date_from = next.date_to
    }
    props.onChange(next)
  }

  const products = (options?.products ?? []).filter((p) => !filters.category || p.category === filters.category)

  return (
    <div className="sticky top-0 z-20 border-b border-edge bg-page print:hidden">
      <div className="mx-auto flex max-w-7xl flex-wrap items-end gap-3 px-4 py-3 sm:px-6">
        <Field label="From">
          <input type="date" className="field" value={filters.date_from} min={options?.date_min ?? undefined} max={options?.date_max ?? undefined} onChange={(e) => set({ date_from: e.target.value })} />
        </Field>
        <Field label="To">
          <input type="date" className="field" value={filters.date_to} min={options?.date_min ?? undefined} max={options?.date_max ?? undefined} onChange={(e) => set({ date_to: e.target.value })} />
        </Field>
        <Field label="Category">
          <select className="field" value={filters.category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">All categories</option>
            {options?.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Product">
          <select className="field" value={filters.product} onChange={(e) => set({ product: e.target.value })}>
            <option value="">All products</option>
            {products.map((p) => (
              <option key={p.product} value={p.product}>
                {p.product}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Region">
          <select className="field" value={filters.region} onChange={(e) => set({ region: e.target.value })}>
            <option value="">All regions</option>
            {options?.regions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
        <button type="button" className="btn" disabled={!isFiltered(filters)} onClick={() => props.onChange(EMPTY_FILTERS)}>
          Reset filters
        </button>
      </div>
    </div>
  )
}
