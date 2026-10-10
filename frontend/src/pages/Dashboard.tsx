import { useEffect, useMemo, useState } from 'react'
import { OverviewChart } from '../charts/OverviewChart'
import { AccuracySection } from '../components/AccuracySection'
import { DataQuality } from '../components/DataQuality'
import { FilterBar } from '../components/FilterBar'
import { ForecastSection } from '../components/ForecastSection'
import { InsightsSection } from '../components/InsightsSection'
import { KpiStrip } from '../components/KpiStrip'
import { ProductsSection } from '../components/ProductsSection'
import { ProfitSection } from '../components/ProfitSection'
import { SalesTable } from '../components/SalesTable'
import { SeasonalitySection } from '../components/SeasonalitySection'
import { ChartCard, EmptyState, Notice, RankBars, Section, Segmented } from '../components/ui'
import { APP_NAME, DATASET_NOTE } from '../config'
import { useApi } from '../hooks/useApi'
import { buildOverviewRows, type Metric } from '../lib/chartData'
import { compactMoney, compactNum, money, money2, num, pct, periodLabel } from '../lib/format'
import { EMPTY_FILTERS, api, isFiltered, type Filters, type Granularity, type GroupItem, type Horizon } from '../services/api'

const METRICS: Record<Metric, { label: string; format: (n: number | null) => string; axis: (n: number) => string }> = {
  revenue: { label: 'Revenue', format: money, axis: compactMoney },
  units: { label: 'Units sold', format: num, axis: compactNum },
  orders: { label: 'Orders', format: num, axis: compactNum },
}

const NAV = [
  ['overview', 'Overview'],
  ['products', 'Products'],
  ['seasonality', 'Seasonality'],
  ['forecast', 'Forecast'],
  ['insights', 'Insights'],
  ['data', 'Data'],
] as const

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === 'dark' || (!document.documentElement.dataset.theme && window.matchMedia?.('(prefers-color-scheme: dark)').matches))
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    try {
      localStorage.setItem('salescast-theme', dark ? 'dark' : 'light')
    } catch {
      /* storage can be unavailable (private window); the theme still applies for this visit */
    }
  }, [dark])
  return { dark, toggle: () => setDark((d) => !d) }
}

function groupBars(items: GroupItem[] | undefined, extra: (i: GroupItem) => string) {
  return (items ?? []).map((i) => ({ name: i.name, value: i.revenue, label: `${money(i.revenue)} (${pct(i.pct_of_revenue)})`, sub: extra(i) }))
}

export default function Dashboard() {
  const theme = useTheme()
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [metric, setMetric] = useState<Metric>('revenue')
  const [granularity, setGranularity] = useState<Granularity>('month')
  const [horizon, setHorizon] = useState<Horizon>(6)

  const key = JSON.stringify(filters)
  const options = useApi((s) => api.filters(s), 'options')
  const dash = useApi((s) => api.dashboard(filters, s), key)
  const cats = useApi((s) => api.categories(filters, s), key)
  const regs = useApi((s) => api.regions(filters, s), key)
  const prods = useApi((s) => api.products(filters, s), key)
  const trends = useApi((s) => api.trends(filters, granularity, s), `${key}|${granularity}`)
  const forecast = useApi((s) => api.forecast(filters, horizon, s), `${key}|${horizon}`)
  // Fit the forecast once first; accuracy and insights reuse the server-side result instead of fitting again.
  const afterForecast = !forecast.loading
  const accuracy = useApi((s) => api.accuracy(filters, horizon, s), `${key}|${horizon}`, afterForecast)
  const insights = useApi((s) => api.insights(filters, horizon, s), `${key}|${horizon}`, afterForecast)

  const kpis = dash.data?.kpis ?? null
  const noSales = kpis !== null && kpis.total_orders === 0
  const rows = useMemo(() => buildOverviewRows(trends.data?.series ?? [], metric), [trends.data, metric])
  const m = METRICS[metric]
  const showAvg = metric === 'revenue' && granularity === 'month'
  const partial = (trends.data?.series ?? []).filter((p) => p.partial).map((p) => periodLabel(p.period))

  return (
    <div className="min-h-screen">
      <header className="border-b border-edge">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{APP_NAME}</h1>
            <p className="hint">Historical sales, a tested forecast, and what to prepare for.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <nav aria-label="Sections" className="hidden gap-3 text-sm md:flex">
              {NAV.map(([id, label]) => (
                <a key={id} href={`#${id}`} className="text-ink-2 hover:text-ink hover:underline">
                  {label}
                </a>
              ))}
            </nav>
            <button type="button" className="btn" aria-pressed={theme.dark} onClick={theme.toggle}>
              {theme.dark ? 'Light theme' : 'Dark theme'}
            </button>
          </div>
        </div>
        {DATASET_NOTE && (
          <div className="mx-auto max-w-7xl px-4 pb-3 sm:px-6">
            <Notice title="Demo data">{DATASET_NOTE}</Notice>
          </div>
        )}
      </header>

      <FilterBar options={options.data} filters={filters} onChange={setFilters} />

      <main className="mx-auto max-w-7xl space-y-12 px-4 py-8 sm:px-6">
        {(options.error || dash.error) && !dash.data && (
          <Notice tone="error" title="Cannot reach the API">
            {options.error ?? dash.error}. Start the stack with <code>docker compose up --build</code> and reload this page.
          </Notice>
        )}
        {isFiltered(filters) && <Notice>Filters are applied. Every number, chart and forecast below covers only the filtered sales.</Notice>}
        {noSales && <Notice tone="warn" title="No sales">No orders match these filters. Widen the date range or reset the filters.</Notice>}

        <Section id="overview" title="Sales overview" description="How much was sold, and how it changed over time.">
          <div className="space-y-4">
            <KpiStrip kpis={kpis} loading={dash.loading} />

            <ChartCard
              title={`${m.label} over time`}
              subtitle={trends.data?.trend.message}
              legend={[
                { label: m.label, color: 'var(--s1)' },
                ...(showAvg ? [{ label: '3-month moving average', color: 'var(--s2)' }] : []),
                ...(metric === 'revenue' ? [{ label: 'Trend line', color: 'var(--ink-2)', dashed: true }] : []),
              ]}
              table={{ columns: ['Period', m.label], rows: rows.map((r) => [periodLabel(r.period), m.format(r.value)]) }}
              busy={trends.loading}
            >
              <div className="mb-3 flex flex-wrap gap-3">
                <Segmented<Metric> label="Measure" value={metric} onChange={setMetric} options={[{ value: 'revenue', label: 'Revenue' }, { value: 'units', label: 'Units sold' }, { value: 'orders', label: 'Orders' }]} />
                <Segmented<Granularity> label="Group by" value={granularity} onChange={setGranularity} options={[{ value: 'month', label: 'Month' }, { value: 'quarter', label: 'Quarter' }, { value: 'year', label: 'Year' }]} />
              </div>
              <OverviewChart rows={rows} label={m.label} format={m.format} formatAxis={m.axis} showMovingAvg={showAvg} showTrend={metric === 'revenue'} />
              {partial.length > 0 && <p className="hint mt-2">{partial.join(', ')} only partly fall inside the date filter, so they are left out of the trend line.</p>}
            </ChartCard>

            <div className="grid gap-4 lg:grid-cols-2">
              <ChartCard
                title="Sales by category"
                subtitle="Highest revenue first, with each category's share of the total."
                table={{ columns: ['Category', 'Revenue', 'Share of revenue', 'Units sold'], rows: (cats.data?.items ?? []).map((c) => [c.name, money(c.revenue), pct(c.pct_of_revenue), num(c.units)]) }}
                busy={cats.loading}
              >
                <RankBars items={groupBars(cats.data?.items, (c) => `${num(c.units)} units sold`)} />
              </ChartCard>
              <ChartCard
                title="Sales by region"
                subtitle="Revenue by region, highest first."
                table={{ columns: ['Region', 'Revenue', 'Orders', 'Units sold', 'Average order value'], rows: (regs.data?.items ?? []).map((r) => [r.name, money(r.revenue), num(r.orders), num(r.units), money2(r.average_order_value)]) }}
                busy={regs.loading}
              >
                <RankBars items={groupBars(regs.data?.items, (r) => `${num(r.orders)} orders, ${num(r.units)} units, average order ${money2(r.average_order_value)}`)} />
              </ChartCard>
            </div>
          </div>
        </Section>

        <Section id="products" title="Products" description="Which products earn the most, sell the most, and sell the least.">
          <ProductsSection data={prods.data} loading={prods.loading} />
        </Section>

        <Section id="seasonality" title="Seasonality and trend" description="Whether sales follow a recurring yearly pattern. A pattern is only reported when the history supports it.">
          <SeasonalitySection data={trends.data} loading={trends.loading} />
        </Section>

        {kpis?.profit && (
          <Section id="profit" title="Profit" description="Profit and margin from the dataset's own cost figures.">
            <ProfitSection categories={cats.data?.items ?? []} regions={regs.data?.items ?? []} products={prods.data?.items ?? []} />
          </Section>
        )}

        <Section
          id="forecast"
          title="Sales forecast"
          description="Expected monthly revenue, with the uncertainty shown. These are estimates, not guarantees."
          actions={
            <Segmented<Horizon> label="Forecast horizon" value={horizon} onChange={setHorizon} options={[{ value: 3, label: '3 months' }, { value: 6, label: '6 months' }, { value: 12, label: '12 months' }]} />
          }
        >
          <ForecastSection data={forecast.data} loading={forecast.loading} error={forecast.error} />
        </Section>

        <Section id="accuracy" title="Forecast accuracy" description="The model is scored on months it was not trained on, and compared with simple baselines.">
          <AccuracySection data={accuracy.data} loading={accuracy.loading} error={accuracy.error} />
        </Section>

        <Section id="insights" title="Insights and recommendations" description="What the data and the forecast suggest management should prepare for.">
          <InsightsSection data={insights.data} loading={insights.loading} error={insights.error} />
        </Section>

        <Section id="data" title="Sales data" description="Every order behind these numbers.">
          <div className="space-y-4">
            <SalesTable filters={filters} />
            <details>
              <summary className="card-title cursor-pointer">Data quality summary</summary>
              <div className="mt-3">
                <DataQuality />
              </div>
            </details>
          </div>
        </Section>

        {!dash.data && !dash.error && <EmptyState>Loading...</EmptyState>}
      </main>

      <footer className="border-t border-edge">
        <div className="mx-auto max-w-7xl space-y-1 px-4 py-6 text-sm text-ink-2 sm:px-6">
          {DATASET_NOTE && <p>{DATASET_NOTE}</p>}
          <p>Forecast values are estimates based on historical patterns and may differ from actual future sales.</p>
        </div>
      </footer>
    </div>
  )
}
