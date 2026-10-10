"""
Tests for the forecasting pipeline.

Most tests inject a deterministic stand-in for the statsmodels fitter, so they verify everything
AROUND the model (data prep, train/test split, metrics, baselines, scope labels, insights,
inventory signal) without needing statsmodels. The last test fits the real model and is skipped
when statsmodels is not installed.

    python tests/test_forecasting.py      (or: pytest tests)
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_analytics import ALL, DF, RUN, close  # noqa: E402  (shares the SQLite copy of the dataset)

from app.analytics import queries, trends  # noqa: E402
from app.analytics.queries import Filters  # noqa: E402
from app.forecasting import insights, model  # noqa: E402


class Skip(Exception):
    pass


def skip(reason):
    try:
        import pytest
        pytest.skip(reason)
    except ImportError:
        raise Skip(reason)


CALLS = []


def stub_fit(y, h, seasonal, alpha):
    """Stand-in for fit_ets: same month last year x 1.02, with a +/-10% band."""
    CALLS.append({"n": len(y), "h": h, "seasonal": seasonal})
    base = y.iloc[-12:].to_numpy(dtype=float)
    mean = np.array([base[i % 12] for i in range(h)]) * 1.02
    idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    frame = pd.DataFrame({"mean": mean, "lower": mean * 0.9, "upper": mean * 1.1}, index=idx)
    return frame, {"model": "STUB", "description": "stub model", "seasonal": seasonal, "fallbacks": []}


def rows(f=ALL):
    return queries.daily_series(RUN, f)


def build(f=ALL, horizon=6):
    return model.build_forecast(rows(f), f, horizon, fit_fn=stub_fit)


# --------------------------------------------------------------------------
def test_error_metrics():
    m = model.error_metrics([100, 200], [110, 180])
    close(m["mae"], 15, 1e-9)
    close(m["rmse"], (500 / 2) ** 0.5, 1e-9)
    close(m["mape_pct"], 10, 1e-9)
    z = model.error_metrics([0, 100], [10, 100])          # zero actuals are excluded from MAPE only
    close(z["mape_pct"], 0, 1e-9)
    assert z["mae"] == 5


def test_split_sizes():
    for n, (tr, te) in {48: (38, 10), 18: (14, 4), 24: (19, 5), 15: (12, 3)}.items():
        s = pd.Series(range(n), index=pd.date_range("2022-01-01", periods=n, freq="MS"), dtype=float)
        a, b = model.split_train_test(s)
        assert (len(a), len(b)) == (tr, te), n
        assert a.index[-1] < b.index[0]                    # chronological, no leakage


def test_baselines():
    s = pd.Series(np.arange(1.0, 25.0), index=pd.date_range("2022-01-01", periods=24, freq="MS"))
    assert list(model.naive_forecast(s, 3)) == [24.0] * 3
    sn = model.seasonal_naive_forecast(s, 14)
    assert list(sn[:3]) == [13.0, 14.0, 15.0] and sn[12] == 13.0     # repeats the last 12 months
    assert model.seasonal_naive_forecast(s.iloc[:8], 3) is None


def test_complete_months_and_exclusions():
    series, notes = model.complete_monthly_series(rows(), ALL)
    assert len(series) == 48 and notes == []
    assert series.index.freqstr == "MS"
    close(series.sum(), DF.sales.sum(), 0.1)

    f = Filters(date_from=date(2023, 1, 15))                        # filter cuts January 2023 in half
    s2, n2 = model.complete_monthly_series(rows(f), f)
    assert s2.index[0] == pd.Timestamp("2023-02-01") and any("Jan 2023" in n for n in n2)

    cut = [r for r in rows() if str(r["order_date"])[:10] <= "2025-12-20"]   # data ends mid-month
    s3, n3 = model.complete_monthly_series(cut, ALL)
    assert s3.index[-1] == pd.Timestamp("2025-11-01") and any("Dec 2025" in n for n in n3)


def test_forecast_structure_overall():
    CALLS.clear()
    fc = build()
    assert fc["available"] and fc["scope"]["label"] == "Overall Sales Forecast" and not fc["scope"]["is_filtered"]
    assert fc["horizon_months"] == 6 and len(fc["forecast"]) == 6
    assert [r["period"] for r in fc["forecast"]] == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert all(r["lower"] <= r["forecast"] <= r["upper"] for r in fc["forecast"])
    assert fc["disclaimer"].startswith("Forecast values are estimates")
    assert len(fc["history"]) == 48 and fc["history"][-1]["period"] == "2025-12"
    # evaluation fit uses the training window only; the final fit uses all months
    assert CALLS[0]["n"] == 38 and CALLS[0]["h"] == 10 and CALLS[1]["n"] == 48 and CALLS[1]["h"] == 6
    assert fc["model"]["seasonality_detected"] and CALLS[0]["seasonal"] and CALLS[1]["seasonal"]


def test_accuracy_block():
    acc = build()["accuracy"]
    assert acc["available"] and acc["split"]["train_months"] == 38 and acc["split"]["test_months"] == 10
    assert acc["split"]["train_period"] == ["2022-01", "2025-02"] and acc["split"]["test_period"] == ["2025-03", "2025-12"]
    assert set(acc["metrics"]) == {"holt_winters", "naive", "seasonal_naive"}
    assert all(set(m) == {"mae", "rmse", "mape_pct"} for m in acc["metrics"].values())
    assert len(acc["test_series"]) == 10 and acc["best_model"] in acc["metrics"]
    # recompute the stand-in model's score independently from the raw data
    monthly = DF.set_index("order_date").sales.resample("MS").sum()
    train, test = monthly.iloc[:38], monthly.iloc[38:]
    pred = np.array([train.iloc[-12:].to_numpy()[i % 12] for i in range(10)]) * 1.02
    close(acc["metrics"]["holt_winters"]["mae"], np.abs(test.to_numpy() - pred).mean(), 0.05)
    close(acc["metrics"]["naive"]["mae"], np.abs(test.to_numpy() - train.iloc[-1]).mean(), 0.05)
    assert 0 <= acc["interval_coverage_pct"] <= 100 and acc["verdict"]
    # with strong seasonality the naive baseline must lose to a seasonal model
    assert acc["metrics"]["holt_winters"]["rmse"] < acc["metrics"]["naive"]["rmse"]


def test_filtered_forecast_is_labeled():
    f = Filters(category="Technology", region="West")
    fc = build(f, 3)
    assert fc["scope"]["label"] == "Filtered Sales Forecast" and fc["scope"]["is_filtered"]
    assert "category: Technology" in fc["scope"]["description"] and len(fc["forecast"]) == 3
    close(sum(h["revenue"] for h in fc["history"]),
          DF[(DF.category == "Technology") & (DF.region == "West")].sales.sum(), 0.1)


def test_horizons_and_validation():
    for h in model.HORIZONS:
        assert len(build(ALL, h)["forecast"]) == h
    try:
        build(ALL, 7)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_short_history_refuses_to_forecast():
    f = Filters(date_from=date(2025, 1, 1))
    fc = build(f)
    assert not fc["available"] and fc["forecast"] == [] and "18" in fc["message"]
    assert fc["accuracy"]["available"] is False and len(fc["history"]) == 12


def test_seasonality_flag_follows_the_data():
    CALLS.clear()
    f = Filters(date_from=date(2024, 7, 1))                         # 18 months: too short for seasonality
    fc = build(f)
    assert fc["available"] and not fc["model"]["seasonality_detected"]
    assert not any(c["seasonal"] for c in CALLS)


def test_forecast_summary_math():
    fc = build(ALL, 6)
    s, monthly = fc["summary"], DF.set_index("order_date").sales.resample("MS").sum()
    total = sum(r["forecast"] for r in fc["forecast"])
    close(s["forecast_total"], total, 0.1)
    close(s["previous_period_total"], monthly.iloc[-6:].sum(), 0.1)
    close(s["same_months_last_year_total"], monthly["2025-01":"2025-06"].sum(), 0.1)
    close(s["vs_same_months_last_year_pct"], (total / monthly["2025-01":"2025-06"].sum() - 1) * 100, 0.01)
    close(s["trailing_12m_avg_monthly"], monthly.iloc[-12:].mean(), 0.05)
    assert s["peak_month"]["period"] in {r["period"] for r in fc["forecast"]}


def test_insights_are_computed_from_the_data():
    fc = build(ALL, 12)
    tr = trends.build_trends(rows(), ALL, "month")
    out = insights.build_insights(RUN, ALL, fc, tr)
    assert out["available"] and out["key_insights"] and out["recommendations"]

    top_cat = DF.groupby("category").sales.sum().idxmax()
    assert any(top_cat in i["text"] and "highest share" in i["text"] for i in out["key_insights"])
    assert all({"text", "basis"} <= set(r) for r in out["recommendations"])

    y = out["year_over_year"]                                       # last 12 vs previous 12 months, from pandas
    monthly = DF.set_index("order_date").sales.resample("MS").sum()
    close(y["revenue_pct"], (monthly.iloc[-12:].sum() / monthly.iloc[-24:-12].sum() - 1) * 100, 0.01)

    inv = out["inventory"]                                          # Nov/Dec are strong months in this data
    assert "Nov 2026" in inv["high_demand_months"] and "Dec 2026" in inv["high_demand_months"]
    assert "Jan 2026" in inv["low_demand_months"] and "Jan 2026" not in inv["high_demand_months"]
    base = monthly.iloc[-12:].mean()
    for row, r in zip(inv["by_month"], fc["forecast"]):
        close(row["vs_average_pct"], (r["forecast"] / base - 1) * 100, 0.01)
    assert "Informational" in inv["note"]
    assert "Nov" in out["business_questions"]["should_inventory_increase"] or "Dec" in out["business_questions"]["should_inventory_increase"]


def test_inventory_signal_matches_independent_calculation():
    fc = build(ALL, 6)
    out = insights.build_insights(RUN, ALL, fc, trends.build_trends(rows(), ALL, "month"))
    monthly = DF.set_index("order_date").sales.resample("MS").sum()
    base = monthly.iloc[-12:].mean()
    ratios = {r["period"]: r["forecast"] / base for r in fc["forecast"]}
    expect_high = [pd.Timestamp(p + "-01").strftime("%b %Y") for p, v in ratios.items() if v >= 1.10]
    expect_low = [pd.Timestamp(p + "-01").strftime("%b %Y") for p, v in ratios.items() if v <= 0.90]
    assert out["inventory"]["high_demand_months"] == expect_high
    assert out["inventory"]["low_demand_months"] == expect_low and "Jan 2026" in expect_low
    if expect_high:
        assert any("Prepare additional inventory" in r["text"] for r in out["recommendations"])


def test_no_busy_month_points_to_historical_peaks():
    def flat_fit(y, h, seasonal, alpha):
        idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
        mean = np.full(h, float(y.iloc[-12:].mean()))
        return (pd.DataFrame({"mean": mean, "lower": mean * 0.9, "upper": mean * 1.1}, index=idx),
                {"model": "FLAT", "description": "flat", "seasonal": seasonal, "fallbacks": []})
    fc = model.build_forecast(rows(), ALL, 6, fit_fn=flat_fit)
    out = insights.build_insights(RUN, ALL, fc, trends.build_trends(rows(), ALL, "month"))
    assert out["inventory"]["high_demand_months"] == [] and out["inventory"]["low_demand_months"] == []
    assert any("No month in this forecast window" in r["text"] and "Nov" in r["text"] for r in out["recommendations"])
    assert "Do not rely on the model alone" in " ".join(r["text"] for r in out["recommendations"])  # flat model loses to baselines
    assert out["business_questions"]["upcoming_seasonal_peaks"].startswith("Next historical peak month: November 2026")


def test_insights_when_forecast_unavailable_or_filtered_to_one_category():
    f = Filters(date_from=date(2025, 1, 1))
    short = insights.build_insights(RUN, f, build(f), trends.build_trends(rows(f), f, "month"))
    assert short["available"] and short["inventory"] is None and short["forecast_insights"] == []
    assert any("Widen the filters" in r["text"] for r in short["recommendations"])

    g = Filters(category="Technology")
    one = insights.build_insights(RUN, g, build(g), trends.build_trends(rows(g), g, "month"))
    assert not any("highest share" in i["text"] for i in one["key_insights"])      # trivial with one category

    none = Filters(category="Nope")
    empty = insights.build_insights(RUN, none, build(none), trends.build_trends(rows(none), none, "month"))
    assert empty["available"] is False


def test_real_statsmodels_fit():
    try:
        import statsmodels  # noqa: F401
    except ImportError:
        skip("statsmodels is not installed in this environment")
    fc = model.build_forecast(rows(), ALL, 6)                        # real fit_ets
    assert fc["available"], fc.get("message")
    assert len(fc["forecast"]) == 6 and all(r["lower"] <= r["forecast"] <= r["upper"] for r in fc["forecast"])
    assert all(r["forecast"] > 0 for r in fc["forecast"])
    acc = fc["accuracy"]
    assert acc["metrics"]["holt_winters"]["mape_pct"] < 40, acc["metrics"]
    assert fc["model"]["seasonality_used"], fc["notes"]
    print("   model:", fc["model"]["name"], "| MAPE", acc["metrics"]["holt_winters"]["mape_pct"],
          "| naive MAPE", acc["metrics"]["naive"]["mape_pct"], "| coverage", acc["interval_coverage_pct"])


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = skipped = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Skip as e:
            skipped += 1
            print("SKIP", t.__name__, "->", e)
        except Exception as e:
            failed += 1
            print("FAIL", t.__name__, "->", repr(e))
    print(f"{len(tests) - failed - skipped} passed, {skipped} skipped, {failed} failed")
    sys.exit(1 if failed else 0)
