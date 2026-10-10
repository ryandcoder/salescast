// Pure formatting helpers (no React) so they can be unit-tested with `npm test`.

const usd0 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const usd2 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const int = new Intl.NumberFormat('en-US')

const ok = (n: number | null | undefined): n is number => typeof n === 'number' && Number.isFinite(n)

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const money = (n: number | null | undefined) => (ok(n) ? usd0.format(n) : '-')
export const money2 = (n: number | null | undefined) => (ok(n) ? usd2.format(n) : '-')
export const num = (n: number | null | undefined) => (ok(n) ? int.format(Math.round(n)) : '-')
export const pct = (n: number | null | undefined, digits = 1) => (ok(n) ? `${n.toFixed(digits)}%` : '-')

/** "+3.1%", "-2.0%", "0.0%". A value that rounds to zero carries no sign. */
export function signedPct(n: number | null | undefined, digits = 1): string {
  if (!ok(n)) return '-'
  const r = Number(n.toFixed(digits))
  const body = Math.abs(r).toFixed(digits)
  return r > 0 ? `+${body}%` : r < 0 ? `-${body}%` : `${body}%`
}

function trim(x: number): string {
  const a = Math.abs(x)
  const s = a >= 100 ? x.toFixed(0) : a >= 10 ? x.toFixed(1) : x.toFixed(2)
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s
}

function compact(n: number): string {
  const a = Math.abs(n)
  if (a >= 1e6) return `${trim(n / 1e6)}M`
  if (a >= 1e3) return `${trim(n / 1e3)}k`
  return String(Math.round(n))
}

/** Axis ticks: "$1.5M", "$138k", "$950". */
export const compactMoney = (n: number) => (n < 0 ? `-$${compact(-n)}` : `$${compact(n)}`)
export const compactNum = (n: number) => compact(n)

/** "2025-03" -> "Mar 2025", "2025-Q2" -> "Q2 2025", "2025" -> "2025". */
export function periodLabel(period: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(period)
  if (m) return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`
  const q = /^(\d{4})-Q(\d)$/.exec(period)
  if (q) return `Q${q[2]} ${q[1]}`
  return period
}

/** Short form for chart axes: "Mar 25", "Q2 25", "2025". */
export function axisLabel(period: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(period)
  if (m) return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1].slice(2)}`
  const q = /^(\d{4})-Q(\d)$/.exec(period)
  if (q) return `Q${q[2]} ${q[1].slice(2)}`
  return period
}
