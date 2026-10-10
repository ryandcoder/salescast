"""
Time-series analysis: revenue/units/orders over time, moving average,
trend line, and seasonality. Built with pandas from daily aggregates.

Periods that are cut by the user's date filter are flagged `partial` and
excluded from trend fitting and seasonality, so a half-month never looks
like a sales drop.
"""
from calendar import month_abbr
from typing import Optional

import numpy as np
import pandas as pd

from app.analytics.queries import Filters, _r

GRANULARITIES = {"month": ("MS", 1), "quarter": ("QS", 3), "year": ("YS", 12)}
SEASONALITY_MIN_MONTHS = 24
SEASONALITY_MIN_R2 = 0.5       # share of detrended variation explained by calendar month
SEASONALITY_MIN_AMPLITUDE = 0.15   # highest month index minus lowest must be at least this
PEAK_INDEX, LOW_INDEX = 1.10, 0.90


def monthly_frame(daily_rows: list[dict]) -> pd.DataFrame:
    cols = ["revenue", "units", "orders", "profit"]
    if not daily_rows:
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([]))
    d = pd.DataFrame(daily_rows)
    d["order_date"] = pd.to_datetime(d["order_date"])
    d = d.set_index("order_date")[cols]
    m = d.resample("MS").sum(min_count=1)
    m = m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="MS"))
    m[["revenue", "units", "orders"]] = m[["revenue", "units", "orders"]].fillna(0)
    if m["profit"].notna().any():
        m["profit"] = m["profit"].fillna(0)
    return m


def aggregate(m: pd.DataFrame, granularity: str) -> pd.DataFrame:
    rule, _ = GRANULARITIES[granularity]
    if granularity == "month" or m.empty:
        return m
    out = m[["revenue", "units", "orders"]].resample(rule).sum()
    out["profit"] = m["profit"].resample(rule).sum(min_count=1)
    return out


def partial_flags(index: pd.DatetimeIndex, months: int, f: Filters) -> np.ndarray:
    """True where a period is only partly inside the user's date filter."""
    flags = np.zeros(len(index), dtype=bool)
    if len(index) == 0:
        return flags
    ends = index + pd.DateOffset(months=months) - pd.Timedelta(days=1)
    if f.date_from:
        flags |= np.asarray(index < pd.Timestamp(f.date_from))
    if f.date_to:
        flags |= np.asarray(ends > pd.Timestamp(f.date_to))
    return flags


def label(ts: pd.Timestamp, granularity: str) -> str:
    if granularity == "month":
        return f"{ts:%Y-%m}"
    if granularity == "quarter":
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    return str(ts.year)


def _fit(values: np.ndarray, mask: np.ndarray):
    """Least-squares line over x = 0..n-1 using only masked points."""
    if mask.sum() < 3:
        return None
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x[mask], values[mask], 1)
    fitted = slope * x + intercept
    ss_res = float(((values[mask] - fitted[mask]) ** 2).sum())
    ss_tot = float(((values[mask] - values[mask].mean()) ** 2).sum())
    return fitted, float(slope), (1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def trend_summary(m: pd.DataFrame, partial: np.ndarray) -> dict:
    values = m["revenue"].to_numpy(dtype=float)
    mask = ~partial
    fit = _fit(values, mask)
    if fit is None:
        return {"months_analyzed": int(mask.sum()), "direction": None,
                "message": "At least 3 complete months are needed to estimate a trend."}
    _, slope, r2 = fit
    mean = float(values[mask].mean())
    annual_pct = slope * 12 / mean * 100 if mean else 0.0
    direction = "increasing" if annual_pct > 2 else "decreasing" if annual_pct < -2 else "flat"

    clean = values[mask]
    yoy = None
    if len(clean) >= 24 and clean[-24:-12].sum() > 0:
        yoy = (clean[-12:].sum() / clean[-24:-12].sum() - 1) * 100

    msg = (f"Linear trend over {int(mask.sum())} complete months is {direction}: "
           f"{slope:+,.0f} revenue per month ({annual_pct:+.1f}% per year).")
    if yoy is not None:
        msg += f" The last 12 months are {yoy:+.1f}% versus the 12 months before."
    return {"months_analyzed": int(mask.sum()), "slope_per_month": _r(slope),
            "annualized_growth_pct": _r(annual_pct), "direction": direction,
            "r_squared": _r(r2, 3), "last_12_vs_prior_12_pct": _r(yoy), "message": msg}


def seasonality(m: pd.DataFrame, partial: np.ndarray) -> dict:
    clean = m.loc[~partial]
    n = len(clean)
    avg_by_month = clean["revenue"].groupby(clean.index.month).mean()
    result = {"supported": False, "reason": None, "strength_r2": None, "message": None,
              "peak_months": [], "low_months": [], "months": [], "quarters": [],
              "by_year": {}, "years": []}

    idx = None
    if n < SEASONALITY_MIN_MONTHS:
        result["reason"] = (f"Seasonality needs at least {SEASONALITY_MIN_MONTHS} complete months "
                            f"of history; {n} available.")
    else:
        # Use revenue per day so months of different length (Feb vs Mar) don't look seasonal.
        y = (clean["revenue"] / clean.index.days_in_month).to_numpy(dtype=float)
        fit = _fit(y, np.ones(n, dtype=bool))
        fitted = fit[0] if fit else None
        if fitted is None or (fitted <= 0).any():
            result["reason"] = "Seasonality could not be measured because the trend is not positive throughout."
        else:
            ratio = pd.Series(y / fitted, index=clean.index)
            grp = ratio.groupby(ratio.index.month)
            idx = grp.mean() / grp.mean().mean()
            grand = ratio.mean()
            ss_tot = float(((ratio - grand) ** 2).sum())
            ss_between = float((grp.count() * (grp.mean() - grand) ** 2).sum())
            r2 = ss_between / ss_tot if ss_tot > 0 else 0.0
            result["strength_r2"] = _r(r2, 3)
            amplitude = float(idx.max() - idx.min())
            if r2 < SEASONALITY_MIN_R2:
                result["reason"] = (f"Calendar month explains only {r2:.0%} of the variation around the trend "
                                    f"(threshold {SEASONALITY_MIN_R2:.0%}), so no reliable seasonal pattern is claimed.")
            elif amplitude < SEASONALITY_MIN_AMPLITUDE:
                result["reason"] = (f"The monthly pattern is consistent but tiny (best vs worst month differ by "
                                    f"{amplitude:.0%}), so it is not treated as meaningful seasonality.")
            else:
                result["supported"] = True

    for mo in range(1, 13):
        result["months"].append({
            "month": mo, "name": month_abbr[mo],
            "average_revenue": _r(avg_by_month.get(mo)),
            "index": _r(idx.get(mo), 3) if idx is not None else None})

    if result["supported"]:
        ranked = [(mo["index"], mo["name"]) for mo in result["months"]]
        result["peak_months"] = [nm for ix, nm in sorted(ranked, reverse=True) if ix >= PEAK_INDEX]
        result["low_months"] = [nm for ix, nm in sorted(ranked) if ix <= LOW_INDEX]
        result["message"] = (f"Revenue follows a recurring yearly pattern (calendar month explains "
                             f"{result['strength_r2']:.0%} of the variation around the trend). "
                             f"Strongest months: {', '.join(result['peak_months']) or 'none above +10%'}; "
                             f"weakest: {', '.join(result['low_months']) or 'none below -10%'}.")
    else:
        result["message"] = result["reason"]

    # Month-by-year matrix for a seasonal overlay chart (complete months only)
    for year, g in clean["revenue"].groupby(clean.index.year):
        row = [None] * 12
        for ts, v in g.items():
            row[ts.month - 1] = _r(v)
        result["by_year"][str(year)] = row

    # Average quarterly revenue (quarters with all 3 complete months only)
    q = clean["revenue"].groupby([clean.index.year, (clean.index.month - 1) // 3 + 1]).agg(["sum", "count"])
    q = q[q["count"] == 3]
    if not q.empty:
        qavg = q["sum"].groupby(level=1).mean()
        for qn, v in qavg.items():
            result["quarters"].append({"quarter": f"Q{qn}", "average_revenue": _r(v),
                                       "share_pct": _r(v / qavg.sum() * 100)})

    # Yearly totals for fully complete years, with year-over-year growth
    ys = clean["revenue"].groupby(clean.index.year).agg(["sum", "count"])
    ys = ys[ys["count"] == 12]["sum"]
    prev = None
    for year, v in ys.items():
        result["years"].append({"year": int(year), "revenue": _r(v),
                                "yoy_growth_pct": _r((v / prev - 1) * 100) if prev else None})
        prev = v
    return result


def build_trends(daily_rows: list[dict], f: Filters, granularity: str = "month") -> dict:
    if granularity not in GRANULARITIES:
        raise ValueError(granularity)
    m = monthly_frame(daily_rows)
    if m.empty:
        return {"granularity": granularity, "series": [], "trend": {"direction": None, "message": "No data for the selected filters."},
                "seasonality": {"supported": False, "message": "No data for the selected filters."}}

    month_partial = partial_flags(m.index, 1, f)
    agg = aggregate(m, granularity)
    agg_partial = partial_flags(agg.index, GRANULARITIES[granularity][1], f)

    values = agg["revenue"].to_numpy(dtype=float)
    fit = _fit(values, ~agg_partial)
    trend_line = fit[0] if fit else [None] * len(agg)
    ma = agg["revenue"].rolling(3).mean() if granularity == "month" else None
    has_profit = agg["profit"].notna().any()

    series = []
    for i, (ts, row) in enumerate(agg.iterrows()):
        series.append({
            "period": label(ts, granularity), "start": f"{ts:%Y-%m-%d}",
            "revenue": _r(row["revenue"]), "units": int(row["units"]), "orders": int(row["orders"]),
            "profit": _r(row["profit"]) if has_profit else None,
            "moving_avg_3": _r(ma.iloc[i]) if ma is not None and not agg_partial[i] else None,
            "trend": _r(trend_line[i]) if trend_line is not None and trend_line[i] is not None else None,
            "partial": bool(agg_partial[i])})

    return {"granularity": granularity, "series": series,
            "trend": trend_summary(m, month_partial),
            "seasonality": seasonality(m, month_partial)}
