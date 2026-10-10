"""
Sales forecasting for SalesCast.

Pipeline:  daily sales -> complete monthly revenue -> chronological train/test split
           -> fit on train, score on test (MAE / RMSE / MAPE) against baselines
           -> refit on all history -> forecast the next 3 / 6 / 12 months.

Model: Holt-Winters style exponential smoothing from statsmodels (ETSModel):
damped additive trend, plus 12-month seasonality only when the history supports
it (see trends.seasonality) and the training window holds at least two full
yearly cycles. ETSModel also provides prediction intervals.

All statsmodels calls live in fit_ets(). build_forecast() accepts any function with
the same signature (`fit_fn`), which keeps the surrounding logic testable on its own.
"""
from typing import Callable, Optional

import numpy as np
import pandas as pd

from app.analytics import trends
from app.analytics.queries import Filters, _r

HORIZONS = (3, 6, 12)
DEFAULT_HORIZON = 6
MIN_MONTHS = 18               # complete months needed to forecast and test honestly
MIN_TRAIN_SEASONAL = 24       # two full yearly cycles are needed to estimate seasonality
TEST_FRACTION = 0.2
MIN_TEST_MONTHS = 3
INTERVAL_LEVEL = 0.80
EDGE_TOLERANCE_DAYS = 3       # data may stop/start a few days inside a month and still count as complete
DISCLAIMER = ("Forecast values are estimates based on historical patterns "
              "and may differ from actual future sales.")

FitFn = Callable[[pd.Series, int, bool, float], tuple]


# --------------------------------------------------------------------------
# Scope / data preparation
# --------------------------------------------------------------------------
def scope_info(f: Filters) -> dict:
    if not f.is_filtered():
        return {"is_filtered": False, "label": "Overall Sales Forecast",
                "filters": {}, "description": "All sales in the dataset (no filters applied)."}
    parts = [f"{k.replace('_', ' ')}: {v}" for k, v in f.as_dict().items()]
    return {"is_filtered": True, "label": "Filtered Sales Forecast", "filters": f.as_dict(),
            "description": "Forecast uses only the filtered sales (" + "; ".join(parts) + ")."}


def complete_monthly_series(daily_rows: list[dict], f: Filters) -> tuple[pd.Series, list[str]]:
    """Monthly revenue for complete months only, plus notes on anything excluded."""
    notes: list[str] = []
    m = trends.monthly_frame(daily_rows)
    if m.empty:
        return pd.Series(dtype=float), notes

    partial = trends.partial_flags(m.index, 1, f)
    dates = pd.to_datetime(pd.DataFrame(daily_rows)["order_date"])
    first, last = dates.min(), dates.max()
    if (last + pd.offsets.MonthEnd(0) - last).days > EDGE_TOLERANCE_DAYS:
        partial[m.index.get_loc(last.to_period("M").to_timestamp())] = True
    if (first - first.to_period("M").to_timestamp()).days > EDGE_TOLERANCE_DAYS:
        partial[m.index.get_loc(first.to_period("M").to_timestamp())] = True

    for ts in m.index[partial]:
        notes.append(f"{ts:%b %Y} was excluded from the model because the data or filters cover only part of that month.")
    series = m.loc[~partial, "revenue"].astype(float).asfreq("MS")
    return series, notes


def split_train_test(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    n_test = max(MIN_TEST_MONTHS, int(round(len(series) * TEST_FRACTION)))
    return series.iloc[:-n_test], series.iloc[-n_test:]


# --------------------------------------------------------------------------
# Error metrics and baselines
# --------------------------------------------------------------------------
def error_metrics(actual, predicted) -> dict:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    err = a - p
    nonzero = a != 0
    return {"mae": float(np.abs(err).mean()),
            "rmse": float(np.sqrt((err ** 2).mean())),
            "mape_pct": float(np.abs(err[nonzero] / a[nonzero]).mean() * 100) if nonzero.any() else None}


def naive_forecast(train: pd.Series, n: int) -> np.ndarray:
    """Last observed month repeated for every future month."""
    return np.repeat(float(train.iloc[-1]), n)


def seasonal_naive_forecast(train: pd.Series, n: int) -> Optional[np.ndarray]:
    """Each future month = the same calendar month one year earlier."""
    if len(train) < 12:
        return None
    base = train.iloc[-12:].to_numpy(dtype=float)
    return np.array([base[i % 12] for i in range(n)])


def _round_metrics(m: dict) -> dict:
    return {"mae": _r(m["mae"]), "rmse": _r(m["rmse"]), "mape_pct": _r(m["mape_pct"])}


def _quality_label(mape: Optional[float]) -> Optional[str]:
    if mape is None:
        return None
    return ("highly accurate" if mape < 10 else "good" if mape < 20
            else "reasonable" if mape < 50 else "inaccurate")


# --------------------------------------------------------------------------
# The statsmodels part
# --------------------------------------------------------------------------
def fit_ets(y: pd.Series, h: int, seasonal: bool, alpha: float) -> tuple[pd.DataFrame, dict]:
    """
    Fit exponential smoothing on `y` (monthly, ascending) and forecast `h` months.
    Returns (frame with columns mean/lower/upper indexed by month start, info dict).

    Tries the richest configuration first and falls back to simpler ones if a fit
    fails or produces non-finite numbers; the fallback is reported in `info`.
    """
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    y = y.astype(float).asfreq("MS")
    attempts: list[tuple[str, Optional[str]]] = []   # (error type, seasonal type)
    if seasonal:
        if (y > 0).all():
            attempts.append(("mul", "mul"))
        attempts.append(("add", "add"))
    attempts.append(("add", None))

    failures: list[str] = []
    for error, seas in attempts:
        try:
            model = ETSModel(y, error=error, trend="add", damped_trend=True,
                             seasonal=seas, seasonal_periods=12 if seas else None)
            res = model.fit(disp=False, maxiter=2000)
            try:
                pred = res.get_prediction(start=len(y), end=len(y) + h - 1,
                                          simulate_repetitions=2000, random_state=42)
            except TypeError:
                pred = res.get_prediction(start=len(y), end=len(y) + h - 1)
            frame = pred.summary_frame(alpha=alpha)
            lower_col = next(c for c in frame.columns if "lower" in str(c))
            upper_col = next(c for c in frame.columns if "upper" in str(c))
            mean = frame["mean"].to_numpy(dtype=float)
            lower = frame[lower_col].to_numpy(dtype=float)
            upper = frame[upper_col].to_numpy(dtype=float)
            if not np.isfinite(np.concatenate([mean, lower, upper])).all():
                raise ValueError("model produced non-finite values")

            mean = np.clip(mean, 0, None)
            lower = np.clip(np.minimum(lower, mean), 0, None)
            upper = np.maximum(upper, mean)
            index = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
            code = f"ETS({error[0].upper()},Ad,{seas[0].upper() if seas else 'N'})"
            desc = ("Holt-Winters exponential smoothing, damped additive trend, "
                    + (f"{'multiplicative' if seas == 'mul' else 'additive'} 12-month seasonality"
                       if seas else "no seasonal component"))
            return (pd.DataFrame({"mean": mean, "lower": lower, "upper": upper}, index=index),
                    {"model": code, "description": desc, "seasonal": seas is not None,
                     "fallbacks": failures})
        except Exception as exc:                                  # try the next, simpler configuration
            failures.append(f"ETS(error={error}, seasonal={seas}) failed: {type(exc).__name__}: {exc}")
    raise RuntimeError("No exponential smoothing configuration could be fitted. " + " | ".join(failures))


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def _history(series: pd.Series) -> list[dict]:
    return [{"period": f"{ts:%Y-%m}", "start": f"{ts:%Y-%m-%d}", "revenue": _r(v)} for ts, v in series.items()]


def forecast_summary(series: pd.Series, fc: pd.DataFrame) -> dict:
    h = len(fc)
    total = float(fc["mean"].sum())
    out = {"months": h, "forecast_total": _r(total),
           "trailing_12m_avg_monthly": _r(series.iloc[-12:].mean()),
           "previous_period_total": None, "vs_previous_period_pct": None,
           "same_months_last_year_total": None, "vs_same_months_last_year_pct": None,
           "next_quarter_vs_previous_quarter_pct": None}

    if len(series) >= h:
        prev = float(series.iloc[-h:].sum())
        out["previous_period_total"] = _r(prev)
        out["vs_previous_period_pct"] = _r((total / prev - 1) * 100) if prev > 0 else None

    year_ago = series.reindex(fc.index - pd.DateOffset(years=1))
    if year_ago.notna().all() and year_ago.sum() > 0:
        out["same_months_last_year_total"] = _r(year_ago.sum())
        out["vs_same_months_last_year_pct"] = _r((total / year_ago.sum() - 1) * 100)

    if h >= 3 and len(series) >= 3 and series.iloc[-3:].sum() > 0:
        out["next_quarter_vs_previous_quarter_pct"] = _r(
            (fc["mean"].iloc[:3].sum() / series.iloc[-3:].sum() - 1) * 100)

    peak, trough = fc["mean"].idxmax(), fc["mean"].idxmin()
    out["peak_month"] = {"period": f"{peak:%Y-%m}", "label": f"{peak:%b %Y}", "value": _r(fc["mean"].max())}
    out["lowest_month"] = {"period": f"{trough:%Y-%m}", "label": f"{trough:%b %Y}", "value": _r(fc["mean"].min())}
    width = ((fc["upper"] - fc["lower"]) / fc["mean"].replace(0, np.nan)).mean() * 100
    out["avg_interval_width_pct"] = _r(width)
    return out


def _accuracy(train, test, fc_test, use_seasonal, season_supported) -> dict:
    actual = test.to_numpy(dtype=float)
    hw = fc_test["mean"].to_numpy(dtype=float)
    naive = naive_forecast(train, len(test))
    snaive = seasonal_naive_forecast(train, len(test))

    scores = {"holt_winters": error_metrics(actual, hw), "naive": error_metrics(actual, naive)}
    if snaive is not None:
        scores["seasonal_naive"] = error_metrics(actual, snaive)

    covered = (actual >= fc_test["lower"].to_numpy()) & (actual <= fc_test["upper"].to_numpy())
    best = min(scores, key=lambda k: scores[k]["rmse"])
    imp = (1 - scores["holt_winters"]["rmse"] / scores["naive"]["rmse"]) * 100 if scores["naive"]["rmse"] > 0 else None

    if best == "holt_winters":
        verdict = (f"Holt-Winters had the lowest error of the models compared "
                   f"(RMSE {imp:.0f}% below the naive baseline).")
    elif imp is not None and imp > 0:
        verdict = (f"Holt-Winters beat the naive baseline (RMSE {imp:.0f}% lower) but not the "
                   f"seasonal-naive baseline, so a simple same-month-last-year rule did as well or better on this test period.")
    else:
        verdict = ("Holt-Winters did not beat the naive baseline on this test period, "
                   "so treat the forecast as indicative only.")

    mape = scores["holt_winters"]["mape_pct"]
    limitations = [
        f"The test period is only {len(test)} months, so these error figures are noisy.",
        "Metrics measure past accuracy; they do not guarantee future accuracy.",
        "The model uses sales history only; promotions, pricing changes and external events are not modeled.",
    ]
    if not use_seasonal:
        limitations.append("No seasonal component was used (history too short or no reliable seasonal pattern)."
                           if not season_supported else
                           "Seasonality was detected but the training window was too short to estimate it reliably.")

    test_rows = []
    for i, (ts, a) in enumerate(test.items()):
        test_rows.append({"period": f"{ts:%Y-%m}", "actual": _r(a), "holt_winters": _r(hw[i]),
                          "lower": _r(fc_test["lower"].iloc[i]), "upper": _r(fc_test["upper"].iloc[i]),
                          "naive": _r(naive[i]),
                          "seasonal_naive": _r(snaive[i]) if snaive is not None else None})

    return {
        "available": True,
        "split": {"train_months": len(train), "test_months": len(test),
                  "train_period": [f"{train.index[0]:%Y-%m}", f"{train.index[-1]:%Y-%m}"],
                  "test_period": [f"{test.index[0]:%Y-%m}", f"{test.index[-1]:%Y-%m}"],
                  "test_share_pct": _r(len(test) / (len(train) + len(test)) * 100)},
        "metrics": {k: _round_metrics(v) for k, v in scores.items()},
        "best_model": best,
        "rmse_improvement_vs_naive_pct": _r(imp),
        "interval_coverage_pct": _r(covered.mean() * 100),
        "interval_level_pct": int(INTERVAL_LEVEL * 100),
        "quality": _quality_label(mape),
        "verdict": verdict,
        "test_series": test_rows,
        "explanations": {
            "mae": "Mean Absolute Error: the average size of the monthly miss, in revenue units. Lower is better.",
            "rmse": "Root Mean Squared Error: like MAE but penalises large misses more. Lower is better.",
            "mape": "Mean Absolute Percentage Error: the average miss as a percentage of actual revenue.",
            "naive": "Naive baseline: repeats the last observed month for every future month.",
            "seasonal_naive": "Seasonal-naive baseline: uses the same month one year earlier.",
            "interval_coverage": f"Share of test months whose actual revenue fell inside the {int(INTERVAL_LEVEL * 100)}% prediction interval.",
        },
        "limitations": limitations,
    }


def build_forecast(daily_rows: list[dict], f: Filters, horizon: int = DEFAULT_HORIZON,
                   fit_fn: FitFn = fit_ets) -> dict:
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")

    series, notes = complete_monthly_series(daily_rows, f)
    base = {"scope": scope_info(f), "horizon_months": horizon,
            "interval_level_pct": int(INTERVAL_LEVEL * 100), "disclaimer": DISCLAIMER, "notes": notes,
            "history": _history(series)}

    if len(series) < MIN_MONTHS:
        msg = (f"A forecast needs at least {MIN_MONTHS} complete months of history so the model can be "
               f"tested on unseen data; {len(series)} available for the current selection.")
        return {**base, "available": False, "message": msg, "forecast": [],
                "summary": None, "model": None, "accuracy": {"available": False, "message": msg}}

    season = trends.seasonality(series.to_frame("revenue"), np.zeros(len(series), dtype=bool))
    train, test = split_train_test(series)
    use_seasonal = bool(season["supported"]) and len(train) >= MIN_TRAIN_SEASONAL
    alpha = 1 - INTERVAL_LEVEL

    # 1) evaluate on unseen data   2) refit on everything   3) forecast the future
    fc_test, info_test = fit_fn(train, len(test), use_seasonal, alpha)
    accuracy = _accuracy(train, test, fc_test, use_seasonal, bool(season["supported"]))
    fc, info = fit_fn(series, horizon, use_seasonal, alpha)

    if info["seasonal"] != use_seasonal or info_test["seasonal"] != use_seasonal:
        notes.append("The seasonal model could not be fitted, so a simpler model without seasonality was used.")
    for failure in info.get("fallbacks", []):
        notes.append(failure)

    forecast_rows = [{"period": f"{ts:%Y-%m}", "start": f"{ts:%Y-%m-%d}", "forecast": _r(r["mean"]),
                      "lower": _r(r["lower"]), "upper": _r(r["upper"])} for ts, r in fc.iterrows()]

    return {**base, "available": True, "forecast": forecast_rows,
            "summary": forecast_summary(series, fc),
            "model": {"name": info["model"], "description": info["description"],
                      "seasonality_detected": bool(season["supported"]),
                      "seasonality_used": bool(info["seasonal"]),
                      "seasonality_message": season["message"],
                      "training_months": len(series), "evaluated_on_months": len(test)},
            "accuracy": accuracy,
            "accuracy_headline": {"mape_pct": accuracy["metrics"]["holt_winters"]["mape_pct"],
                                  "quality": accuracy["quality"], "verdict": accuracy["verdict"]}}
