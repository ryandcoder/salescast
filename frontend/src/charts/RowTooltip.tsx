import type { ReactNode } from 'react'

export const TICK = { fill: 'var(--muted)', fontSize: 12 }

/** Tooltip shell for Recharts: receives the hovered data row and renders whatever `render` returns. */
export function RowTooltip<T>(props: {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: T }>
  render: (row: T) => ReactNode
}) {
  const row = props.payload?.[0]?.payload
  if (!props.active || !row) return null
  return (
    <div className="rounded-lg border border-edge bg-surface px-3 py-2 text-xs text-ink shadow-lg">
      {props.render(row)}
    </div>
  )
}
