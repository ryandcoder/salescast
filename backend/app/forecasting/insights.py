"""
Dynamic insights, business recommendations and the inventory signal.

Every sentence is built from computed numbers (SQL aggregates, the trend and
seasonality analysis, and the forecast). Nothing here is a fixed conclusion:
when the data does not support a statement, the statement is not made.
"""
from dataclasses import replace

import pandas as pd

from app.analytics import queries
from app.analytics.queries import Filters, _r

HIGH_DEMAND_RATIO = 1.10      # forecast month vs trailing-12-month average
LOW_DEMAND_RATIO = 0.90
DECLINE_PCT = -2.0            # category revenue change counted as "declining"
WEAK_REGION_RATIO = 0.80      # region revenue vs the average region
MONEY = "$"


def _money(x) -> str:
    return f"{MONEY}{x:,.0f}"


def _pct(x) -> str:
    return f"{x:+.1f}%"


def _direction(pct, flat_band=2.0) -> str:
    if pct is None:
        return ""
    return "higher" if pct > flat_band else "lower" if pct < -flat_band else "about the same"


def _window(f: Filters, start, end) -> Filters:
    return replace(f, date_from=start.date(), date_to=end.date())


def last_vs_prior_year(run, f: Filters, month_starts: pd.DatetimeIndex):
    """Last 12 complete months vs the 12 before: totals, order/AOV split, per-category change."""
    if len(month_starts) < 24:
        return None
    cur_f = _window(f, month_starts[-12], month_starts[-1] + pd.offsets.MonthEnd(0))
    prev_f = _window(f, month_starts[-24], month_starts[-12] - pd.Timedelta(days=1))
    cur_k, prev_k = queries.kpis(run, cur_f), queries.kpis(run, prev_f)
    if not prev_k["total_revenue"] or not prev_k["total_orders"]:
        return None

    cur_c = {c["name"]: c["revenue"] for c in queries.grouped(run, cur_f, "category")}
    prev_c = {c["name"]: c["revenue"] for c in queries.grouped(run, prev_f, "category")}
    cats = []
    for name in sorted(cur_c.keys() | prev_c.keys()):
        c, p = cur_c.get(name, 0.0), prev_c.get(name, 0.0)
        cats.append({"name": name, "current": _r(c), "previous": _r(p), "delta": _r(c - p),
                     "growth_pct": _r((c / p - 1) * 100) if p > 0 else None})
    cats.sort(key=lambda r: (r["growth_pct"] is None, -(r["growth_pct"] or 0)))

    return {"revenue_pct": _r((cur_k["total_revenue"] / prev_k["total_revenue"] - 1) * 100),
            "orders_pct": _r((cur_k["total_orders"] / prev_k["total_orders"] - 1) * 100),
            "aov_pct": _r((cur_k["average_order_value"] / prev_k["average_order_value"] - 1) * 100),
            "current_revenue": cur_k["total_revenue"], "previous_revenue": prev_k["total_revenue"],
            "categories": cats}


def build_insights(run, f: Filters, fc: dict, tr: dict) -> dict:
    cats = queries.grouped(run, f, "category")
    regs = queries.grouped(run, f, "region")
    prods = queries.grouped(run, f, "product")
    if not cats:
        return {"scope": fc["scope"], "available": False, "message": "No sales match the selected filters.",
                "key_insights": [], "forecast_insights": [], "recommendations": [],
                "inventory": None, "business_questions": {}}

    month_starts = pd.DatetimeIndex([h["start"] for h in fc["history"]])
    yoy = last_vs_prior_year(run, f, month_starts)
    season = tr["seasonality"]
    key: list[dict] = []

    # ---- Historical: what happened? ----------------------------------------
    if len(cats) > 1:
        key.append({"type": "historical",
                    "text": f"{cats[0]['name']} generates the highest share of revenue ({cats[0]['pct_of_revenue']:.1f}%)."})
    if tr["trend"].get("direction"):
        key.append({"type": "historical", "text": tr["trend"]["message"]})
    if season.get("message"):
        key.append({"type": "historical", "text": season["message"]})
    if len(regs) > 1:
        key.append({"type": "historical",
                    "text": (f"{regs[0]['name']} is the strongest region ({regs[0]['pct_of_revenue']:.1f}% of revenue); "
                             f"{regs[-1]['name']} is the weakest ({regs[-1]['pct_of_revenue']:.1f}%).")})
    if prods:
        top_rev, top_units = prods[0], max(prods, key=lambda p: p["units"])
        if top_rev["name"] != top_units["name"]:
            key.append({"type": "historical",
                        "text": (f"{top_rev['name']} earns the most revenue while {top_units['name']} sells the most units: "
                                 f"high volume does not mean high revenue.")})
        else:
            key.append({"type": "historical",
                        "text": f"{top_rev['name']} leads on both revenue and units sold."})
    margins = [c for c in cats if c["profit_margin_pct"] is not None]
    if len(margins) > 1:
        hi, lo = max(margins, key=lambda c: c["profit_margin_pct"]), min(margins, key=lambda c: c["profit_margin_pct"])
        key.append({"type": "historical",
                    "text": (f"{hi['name']} has the highest profit margin ({hi['profit_margin_pct']:.1f}%) and "
                             f"{lo['name']} the lowest ({lo['profit_margin_pct']:.1f}%).")})

    # ---- Diagnostic: what contributed to the change? ------------------------
    diagnostic = "Fewer than 24 complete months are available, so a year-over-year comparison is not possible."
    if yoy:
        driver = "order volume" if abs(yoy["orders_pct"]) >= abs(yoy["aov_pct"]) else "average order value"
        moved = [c for c in yoy["categories"] if c["growth_pct"] is not None]
        top_up = max(moved, key=lambda c: c["delta"], default=None)
        top_down = min(moved, key=lambda c: c["delta"], default=None)
        diagnostic = (f"Revenue over the last 12 months is {_pct(yoy['revenue_pct'])} versus the 12 months before "
                      f"(orders {_pct(yoy['orders_pct'])}, average order value {_pct(yoy['aov_pct'])}), "
                      f"so the change was driven mainly by {driver}.")
        if top_up and top_up["delta"] > 0:
            diagnostic += f" {top_up['name']} added the most revenue ({_money(top_up['delta'])})."
        if top_down and top_down["delta"] < 0 and top_down is not top_up:
            diagnostic += f" {top_down['name']} lost the most ({_money(abs(top_down['delta']))})."
        key.append({"type": "diagnostic", "text": diagnostic})

    # ---- Forecast ------------------------------------------------------------
    fc_insights: list[str] = []
    inventory = None
    s = fc.get("summary")
    acc = fc.get("accuracy") or {}
    if fc["available"]:
        h = s["months"]
        label = fc["scope"]["label"].lower()
        line = f"The {label} for the next {h} months totals about {_money(s['forecast_total'])}"
        if s["vs_same_months_last_year_pct"] is not None:
            line += (f", {_pct(s['vs_same_months_last_year_pct'])} versus the same months last year "
                     f"({_direction(s['vs_same_months_last_year_pct'])}).")
        else:
            line += "."
        fc_insights.append(line)
        if s["vs_previous_period_pct"] is not None:
            fc_insights.append(f"Compared with the previous {h} months it is {_pct(s['vs_previous_period_pct'])}; "
                               f"part of this gap can be seasonal rather than growth.")
        if s["next_quarter_vs_previous_quarter_pct"] is not None:
            fc_insights.append(f"Expected revenue for the next quarter is {_pct(s['next_quarter_vs_previous_quarter_pct'])} "
                               f"versus the last quarter of actuals.")
        if h > 1:
            fc_insights.append(f"The strongest forecast month is {s['peak_month']['label']} ({_money(s['peak_month']['value'])}); "
                               f"the weakest is {s['lowest_month']['label']} ({_money(s['lowest_month']['value'])}).")
        fc_insights.append(f"The {fc['interval_level_pct']}% prediction interval is on average about "
                           f"{s['avg_interval_width_pct']:.0f}% of the forecast wide, so actual sales may differ noticeably.")
        if acc.get("available"):
            m = acc["metrics"]["holt_winters"]
            fc_insights.append(f"On held-out months the model's average error was {m['mape_pct']:.1f}% (MAPE, {acc['quality']}). "
                               f"{acc['verdict']}")
        for text in fc_insights:
            key.append({"type": "forecast", "text": text})

        # ---- Inventory signal (informational only) ---------------------------
        base = s["trailing_12m_avg_monthly"]
        rows = [(r, r["forecast"] / base) for r in fc["forecast"]] if base else []
        label_of = lambda r: pd.Timestamp(r["start"]).strftime("%b %Y")
        high = [label_of(r) for r, ratio in rows if ratio >= HIGH_DEMAND_RATIO]
        low = [label_of(r) for r, ratio in rows if ratio <= LOW_DEMAND_RATIO]
        inventory = {
            "high_demand_months": high, "low_demand_months": low,
            "threshold": (f"High demand = forecast at least {int((HIGH_DEMAND_RATIO - 1) * 100)}% above the trailing "
                          f"12-month average monthly revenue ({_money(base)}); low demand = at least "
                          f"{int((1 - LOW_DEMAND_RATIO) * 100)}% below."),
            "by_month": [{"period": r["period"], "forecast": r["forecast"], "vs_average_pct": _r((ratio - 1) * 100)}
                         for r, ratio in rows],
            "note": ("Informational only. Based on forecast revenue for this selection; it is not a unit-level "
                     "forecast or an inventory optimisation."),
        }

    # ---- Recommendations -----------------------------------------------------
    recs: list[dict] = []
    peaks = season.get("peak_months") or []
    if inventory:
        if inventory["high_demand_months"]:
            recs.append({"text": f"Prepare additional inventory ahead of {', '.join(inventory['high_demand_months'])}.",
                         "basis": "Forecast revenue in these months is well above the trailing 12-month average."})
        elif peaks:
            recs.append({"text": (f"No month in this forecast window is expected to be unusually busy. Historically the "
                                  f"strongest months are {', '.join(peaks)}, so plan stock builds ahead of them."),
                         "basis": season["message"]})
        if inventory["low_demand_months"]:
            recs.append({"text": f"Expect softer demand in {', '.join(inventory['low_demand_months'])}; avoid over-ordering for these months.",
                         "basis": "Forecast revenue in these months is well below the trailing 12-month average."})
    if not recs and not season.get("supported"):
        recs.append({"text": "Use the forecast for short-term planning only; the history shows no reliable seasonal pattern to plan around.",
                     "basis": season.get("message") or ""})

    if yoy:
        declining = [c for c in yoy["categories"] if c["growth_pct"] is not None and c["growth_pct"] <= DECLINE_PCT]
        if declining:
            names = ", ".join(f"{c['name']} ({_pct(c['growth_pct'])})" for c in declining)
            recs.append({"text": f"Monitor categories with declining revenue: {names}.",
                         "basis": "Revenue over the last 12 months compared with the 12 months before."})
        elif len(yoy["categories"]) > 1:
            recs.append({"text": "No category shows declining revenue over the last 12 months; keep tracking category trends as new data arrives.",
                         "basis": "Revenue over the last 12 months compared with the 12 months before."})

    if len(regs) > 1:
        avg_rev = sum(r["revenue"] for r in regs) / len(regs)
        weak = [r for r in regs if r["revenue"] < WEAK_REGION_RATIO * avg_rev]
        if weak:
            names = ", ".join(f"{r['name']} ({r['pct_of_revenue']:.1f}% of revenue)" for r in weak)
            recs.append({"text": f"Review regional performance in {names}; revenue is more than 20% below the regional average.",
                         "basis": "Revenue by region compared with the average region."})
        else:
            recs.append({"text": "Regional revenue is reasonably balanced (no region is more than 20% below the regional average).",
                         "basis": "Revenue by region compared with the average region."})

    if len(margins) > 1:
        hi = max(margins, key=lambda c: c["profit_margin_pct"])
        recs.append({"text": f"Protect stock availability for {hi['name']}, the highest-margin category ({hi['profit_margin_pct']:.1f}%).",
                     "basis": "Profit margin by category."})

    if acc.get("available"):
        if acc["best_model"] != "holt_winters":
            recs.append({"text": "Do not rely on the model alone; a simple baseline matched or beat it on the test period. Use it alongside last year's same-month sales.",
                         "basis": acc["verdict"]})
        else:
            recs.append({"text": (f"Use the forecast as a planning range, not a target: past error averaged "
                                  f"{acc['metrics']['holt_winters']['mape_pct']:.1f}% and the {fc['interval_level_pct']}% interval "
                                  f"captured {acc['interval_coverage_pct']:.0f}% of test months."),
                         "basis": acc["verdict"]})
    elif not fc["available"]:
        recs.append({"text": "Widen the filters or date range to forecast: " + fc["message"], "basis": ""})

    # ---- Business questions --------------------------------------------------
    next_peak = None
    if season.get("supported") and fc["available"]:
        idx = {m["month"]: m["index"] for m in season["months"]}
        start = pd.Timestamp(fc["forecast"][0]["start"])
        for k in range(12):                                   # first upcoming month that is a historical peak
            ts = start + pd.DateOffset(months=k)
            if idx.get(ts.month) is not None and idx[ts.month] >= HIGH_DEMAND_RATIO:
                next_peak = f"{ts:%B %Y} (historically {(idx[ts.month] - 1) * 100:+.0f}% versus a typical month)"
                break
    growth_list = ""
    if yoy:
        growth_list = ", ".join(f"{c['name']} {_pct(c['growth_pct'])}" for c in yoy["categories"] if c["growth_pct"] is not None)
    business = {
        "what_happened": (f"Total revenue is {_money(sum(c['revenue'] for c in cats))}. {tr['trend'].get('message', '')}").strip(),
        "what_contributed": diagnostic,
        "what_is_likely": (fc_insights[0] if fc_insights else fc.get("message", "No forecast is available for this selection.")),
        "should_inventory_increase": (
            ("Yes, ahead of " + ", ".join(inventory["high_demand_months"]) + ".") if inventory and inventory["high_demand_months"]
            else "The forecast does not show any month far above the recent average, so it does not call for a general increase."
            if inventory else "Not assessed: no forecast is available for this selection."),
        "categories_expected_to_grow": (
            f"Category-level forecasts are not implemented. Revenue change over the last 12 months: {growth_list}." if growth_list
            else "Not enough history for a category comparison."),
        "months_with_lower_demand": (", ".join(inventory["low_demand_months"]) if inventory and inventory["low_demand_months"]
                                     else "None in the forecast window." if inventory else "Not assessed."),
        "upcoming_seasonal_peaks": (f"Next historical peak month: {next_peak}." if next_peak
                                    else "No historical peak month is coming up in the next 12 months."
                                    if season.get("supported") and fc["available"]
                                    else "No reliable seasonal pattern was detected, so no peaks are claimed."),
    }

    return {"scope": fc["scope"], "available": True, "horizon_months": fc["horizon_months"],
            "key_insights": key, "forecast_insights": fc_insights, "recommendations": recs,
            "inventory": inventory, "business_questions": business,
            "year_over_year": yoy, "disclaimer": fc["disclaimer"]}
