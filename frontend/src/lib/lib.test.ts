import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildForecastRows, buildOverviewRows, buildSeasonalRows, firstForecastPeriod, lastActualPeriod } from './chartData.ts'
import { axisLabel, compactMoney, compactNum, money, num, pct, periodLabel, signedPct } from './format.ts'

test('money, numbers and percentages', () => {
  assert.equal(money(6625754.91), '$6,625,755')
  assert.equal(money(null), '-')
  assert.equal(num(68637), '68,637')
  assert.equal(pct(27.834), '27.8%')
  assert.equal(signedPct(3.14), '+3.1%')
  assert.equal(signedPct(-2), '-2.0%')
  assert.equal(signedPct(-0.04), '0.0%') // rounds to zero: no sign
  assert.equal(signedPct(undefined), '-')
})

test('compact axis labels', () => {
  assert.equal(compactMoney(1_500_000), '$1.5M')
  assert.equal(compactMoney(138_000), '$138k')
  assert.equal(compactMoney(98_800), '$98.8k')
  assert.equal(compactMoney(100_000), '$100k')
  assert.equal(compactMoney(950), '$950')
  assert.equal(compactMoney(0), '$0')
  assert.equal(compactMoney(-12_000), '-$12k')
  assert.equal(compactNum(5521), '5.52k')
})

test('period labels', () => {
  assert.equal(periodLabel('2025-03'), 'Mar 2025')
  assert.equal(periodLabel('2024-Q3'), 'Q3 2024')
  assert.equal(periodLabel('2023'), '2023')
  assert.equal(axisLabel('2025-12'), 'Dec 25')
  assert.equal(axisLabel('2024-Q1'), 'Q1 24')
  assert.equal(axisLabel('2022'), '2022')
})

const trendPoint = (period: string, revenue: number, partial = false) => ({
  period, start: `${period}-01`, revenue, units: revenue / 10, orders: revenue / 100,
  profit: null, moving_avg_3: revenue - 1, trend: revenue + 1, partial,
})

test('overview rows: only revenue has moving average and trend', () => {
  const s = [trendPoint('2025-01', 1000), trendPoint('2025-02', 2000, true)]
  const rev = buildOverviewRows(s, 'revenue')
  assert.deepEqual(rev[0], { period: '2025-01', value: 1000, movingAvg: 999, trend: 1001, partial: false })
  assert.equal(rev[1].partial, true)
  const units = buildOverviewRows(s, 'units')
  assert.equal(units[1].value, 200)
  assert.equal(units[1].movingAvg, null)
  assert.equal(units[1].trend, null)
})

test('forecast rows connect actual to forecast and stack the interval band', () => {
  const history = [
    { period: '2025-11', start: '2025-11-01', revenue: 100 },
    { period: '2025-12', start: '2025-12-01', revenue: 120 },
  ]
  const forecast = [
    { period: '2026-01', start: '2026-01-01', forecast: 90, lower: 80, upper: 105 },
    { period: '2026-02', start: '2026-02-01', forecast: 95, lower: 70, upper: 120 },
  ]
  const rows = buildForecastRows(history, forecast)
  assert.equal(rows.length, 4)
  assert.deepEqual(rows[1], { period: '2025-12', actual: 120, forecast: 120, lower: 120, band: 0, upper: 120, isForecast: false })
  assert.equal(rows[0].forecast, null) // only the LAST actual month is bridged
  assert.deepEqual(rows[2], { period: '2026-01', actual: null, forecast: 90, lower: 80, band: 25, upper: 105, isForecast: true })
  assert.equal(rows[3].lower! + rows[3].band!, rows[3].upper)
  assert.equal(firstForecastPeriod(rows), '2026-01')
  assert.equal(lastActualPeriod(rows), '2025-12')
})

test('forecast rows without a forecast are history only', () => {
  const rows = buildForecastRows([{ period: '2025-12', start: '2025-12-01', revenue: 120 }], [])
  assert.equal(rows.length, 1)
  assert.equal(rows[0].forecast, null)
  assert.equal(firstForecastPeriod(rows), null)
})

test('seasonal rows: latest years only, 12 months, gaps stay null', () => {
  const byYear = { '2022': [1, 2], '2023': [3, 4, 5], '2024': [], '2025': [9], '2021': [0] }
  const { years, rows } = buildSeasonalRows(byYear, 4)
  assert.deepEqual(years, ['2022', '2023', '2024', '2025'])
  assert.equal(rows.length, 12)
  assert.equal(rows[0].month, 'Jan')
  assert.equal(rows[0]['2025'], 9)
  assert.equal(rows[2]['2022'], null)
  assert.equal(rows[11]['2023'], null)
})
