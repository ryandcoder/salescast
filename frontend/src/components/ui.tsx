import { useState, type ReactNode } from 'react'

export function Section(props: {
  id: string
  title: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section id={props.id} aria-labelledby={`${props.id}-title`} className="scroll-mt-24">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <h2 id={`${props.id}-title`} className="text-xl font-semibold tracking-tight">
            {props.title}
          </h2>
          {props.description && <p className="hint mt-1">{props.description}</p>}
        </div>
        {props.actions}
      </div>
      {props.children}
    </section>
  )
}

export function Notice(props: { tone?: 'info' | 'warn' | 'error'; title?: string; children: ReactNode }) {
  const tone = props.tone ?? 'info'
  const label = props.title ?? (tone === 'error' ? 'Error' : tone === 'warn' ? 'Heads up' : 'Note')
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className="rounded-lg border border-edge bg-ghost px-3 py-2 text-sm text-ink"
    >
      <span className="font-semibold">{label}: </span>
      {props.children}
    </div>
  )
}

export function Segmented<T extends string | number>(props: {
  label: string
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div role="group" aria-label={props.label} className="inline-flex rounded-md border border-edge bg-surface p-0.5">
      {props.options.map((o) => {
        const active = o.value === props.value
        return (
          <button
            key={String(o.value)}
            type="button"
            aria-pressed={active}
            onClick={() => props.onChange(o.value)}
            className={`rounded px-3 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-s1 ${
              active ? 'bg-ink text-surface' : 'text-ink-2 hover:bg-ghost'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export interface LegendItem {
  label: string
  color: string
  dashed?: boolean
  box?: boolean
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5">
          {it.box ? (
            <span className="inline-block h-3 w-4 rounded-sm" style={{ background: it.color, opacity: 0.25 }} />
          ) : (
            <span
              className="inline-block w-5 border-t-2"
              style={{ borderColor: it.color, borderTopStyle: it.dashed ? 'dashed' : 'solid' }}
            />
          )}
          {it.label}
        </li>
      ))}
    </ul>
  )
}

export function SimpleTable(props: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr>
            {props.columns.map((c, i) => (
              <th key={c} className={`th sticky top-0 bg-surface ${i === 0 ? '' : 'text-right'}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((r, i) => (
            <tr key={i}>
              {r.map((cell, j) => (
                <td key={j} className={`td tabular-nums ${j === 0 ? '' : 'text-right'}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** A chart panel. Every chart can be flipped to a table, so no value depends on seeing colour or hovering. */
export function ChartCard(props: {
  title: string
  subtitle?: ReactNode
  legend?: LegendItem[]
  table?: { columns: string[]; rows: (string | number)[][] }
  busy?: boolean
  className?: string
  children: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <div className={`card ${props.className ?? ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="card-title">{props.title}</h3>
          {props.subtitle && <p className="hint mt-0.5">{props.subtitle}</p>}
        </div>
        {props.table && (
          <button type="button" className="btn" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? 'Show chart' : 'Show table'}
          </button>
        )}
      </div>
      {props.legend && !asTable && <Legend items={props.legend} />}
      <div className={`mt-3 transition-opacity ${props.busy ? 'opacity-60' : ''}`}>
        {asTable && props.table ? <SimpleTable {...props.table} /> : props.children}
      </div>
    </div>
  )
}

export interface RankItem {
  name: string
  value: number
  label: string
  sub?: string
}

/** Horizontal bars in plain HTML: thin marks, rounded data end, value printed at the end of each row. */
export function RankBars({ items, color = 'var(--s1)' }: { items: RankItem[]; color?: string }) {
  const max = Math.max(0, ...items.map((i) => i.value)) || 1
  if (items.length === 0) return <EmptyState />
  return (
    <ul className="space-y-3">
      {items.map((it) => (
        <li key={it.name}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium">{it.name}</span>
            <span className="shrink-0 tabular-nums">{it.label}</span>
          </div>
          <div className="mt-1 h-2.5 w-full">
            <div
              className="h-full rounded-r-[4px]"
              style={{ width: `${(Math.max(0, it.value) / max) * 100}%`, background: color }}
            />
          </div>
          {it.sub && <div className="mt-0.5 text-xs text-ink-2">{it.sub}</div>}
        </li>
      ))}
    </ul>
  )
}

export function EmptyState({ children }: { children?: ReactNode }) {
  return <p className="py-8 text-center text-sm text-ink-2">{children ?? 'No data for the current filters.'}</p>
}

export function Skeleton({ className = 'h-40' }: { className?: string }) {
  return <div className={`motion-safe:animate-pulse rounded-lg bg-ghost ${className}`} aria-hidden="true" />
}
