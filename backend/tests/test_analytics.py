"""
Checks the SQL layer and time-series logic against plain pandas on the same data.
Runs on SQLite (the SQL is portable), so no PostgreSQL is needed:
    python tests/test_analytics.py      (or: pytest tests)
"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.analytics import queries, trends  # noqa: E402
from app.analytics.cleaning import clean_sales  # noqa: E402
from app.analytics.queries import Filters  # noqa: E402

sqlite3.register_adapter(date, lambda d: d.isoformat())

DF, _ = clean_sales(pd.read_csv(ROOT / "data" / "sales.csv"))


def make_run():
    con = sqlite3.connect(":memory:")
    con.row_factory = lambda cur, row: {d[0]: v for d, v in zip(cur.description, row)}
    out = DF.copy()
    out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
    out.to_sql("sales", con, index=False)
    return lambda sql, params=None: con.execute(sql, params or {}).fetchall()


RUN = make_run()
ALL = Filters()


def close(a, b, tol=0.02):
    assert abs(a - b) <= tol, (a, b)


def test_kpis_match_pandas():
    k = queries.kpis(RUN, ALL)
    close(k["total_revenue"], DF.sales.sum())
    assert k["total_orders"] == DF.order_id.nunique() == len(DF)
    assert k["units_sold"] == DF.quantity.sum()
    close(k["average_order_value"], DF.sales.sum() / len(DF))
    assert k["months_covered"] == 48
    close(k["average_monthly_revenue"], DF.sales.sum() / 48)
    close(k["profit"]["total_profit"], DF.profit.sum())
    assert k["best_product_by_revenue"]["name"] == DF.groupby("product").sales.sum().idxmax()
    assert k["best_product_by_units"]["name"] == DF.groupby("product").quantity.sum().idxmax()
    assert k["best_region"]["name"] == DF.groupby("region").sales.sum().idxmax()


def test_filters_applied():
    f = Filters(date_from=date(2024, 1, 1), date_to=date(2024, 12, 31), category="Technology", region="West")
    sub = DF[(DF.order_date.dt.year == 2024) & (DF.category == "Technology") & (DF.region == "West")]
    k = queries.kpis(RUN, f)
    close(k["total_revenue"], sub.sales.sum())
    assert k["total_orders"] == len(sub)
    assert f.is_filtered() and not ALL.is_filtered()
    empty = queries.kpis(RUN, Filters(category="Nope"))
    assert empty["total_orders"] == 0 and empty["best_region"] is None


def test_groups():
    cats = queries.grouped(RUN, ALL, "category")
    assert [c["revenue"] for c in cats] == sorted([c["revenue"] for c in cats], reverse=True)
    close(sum(c["pct_of_revenue"] for c in cats), 100, 0.1)
    close(cats[0]["revenue"], DF.groupby("category").sales.sum().max())
    prods = queries.grouped(RUN, ALL, "product")
    assert len(prods) == DF["product"].nunique() and "category" in prods[0]
    close(prods[0]["avg_price"], DF[DF["product"] == prods[0]["name"]].unit_price.mean())
    regs = queries.grouped(RUN, ALL, "region")
    assert len(regs) == 4


def test_trends_monthly_match():
    t = trends.build_trends(queries.daily_series(RUN, ALL), ALL, "month")
    expected = DF.set_index("order_date").sales.resample("MS").sum()
    assert len(t["series"]) == len(expected) == 48
    for row, v in zip(t["series"], expected):
        close(row["revenue"], v)
    assert t["series"][0]["moving_avg_3"] is None and t["series"][2]["moving_avg_3"] is not None
    assert all(not r["partial"] for r in t["series"])
    assert t["trend"]["direction"] == "increasing", t["trend"]
    q = trends.build_trends(queries.daily_series(RUN, ALL), ALL, "quarter")
    y = trends.build_trends(queries.daily_series(RUN, ALL), ALL, "year")
    assert len(q["series"]) == 16 and len(y["series"]) == 4
    close(sum(r["revenue"] for r in y["series"]), DF.sales.sum(), 0.1)


def test_seasonality_detected():
    s = trends.build_trends(queries.daily_series(RUN, ALL), ALL)["seasonality"]
    assert s["supported"], s["message"]
    assert "Dec" in s["peak_months"] and "Nov" in s["peak_months"]
    assert "Jan" in s["low_months"] and "Feb" in s["low_months"]
    assert len(s["years"]) == 4 and s["years"][0]["yoy_growth_pct"] is None
    close(sum(q["share_pct"] for q in s["quarters"]), 100, 0.1)


def test_seasonality_not_claimed_without_enough_data():
    f = Filters(date_from=date(2024, 1, 1), date_to=date(2024, 12, 31))
    s = trends.build_trends(queries.daily_series(RUN, f), f)["seasonality"]
    assert not s["supported"] and "24" in s["reason"]


def test_flat_noise_is_not_seasonal():
    rng = np.random.default_rng(1)
    days = pd.date_range("2022-01-01", "2025-12-31", freq="D")
    rows = [{"order_date": d, "revenue": float(rng.normal(1000, 50)), "units": 1, "orders": 1, "profit": None}
            for d in days]
    s = trends.build_trends(rows, ALL)
    assert not s["seasonality"]["supported"], s["seasonality"]["message"]
    assert s["trend"]["direction"] == "flat", s["trend"]


def test_partial_months_flagged_and_excluded():
    f = Filters(date_from=date(2023, 1, 15), date_to=date(2025, 12, 31))
    t = trends.build_trends(queries.daily_series(RUN, f), f)
    assert t["series"][0]["partial"] and not t["series"][1]["partial"]
    assert t["trend"]["months_analyzed"] == 35


def test_sales_table():
    p = queries.sales_page(RUN, ALL, None, "sales", "desc", 1, 10)
    assert p["total"] == len(DF) and len(p["items"]) == 10
    assert p["items"][0]["sales"] == DF.sales.max()
    s = queries.sales_page(RUN, ALL, "laptop", "order_date", "asc", 1, 5)
    assert all(i["product"] == "Laptop" for i in s["items"])
    assert s["total"] == (DF["product"] == "Laptop").sum()
    p2 = queries.sales_page(RUN, ALL, None, "order_id", "asc", 2, 10)
    assert p2["items"][0]["order_id"] == DF.sort_values("order_id").iloc[10].order_id
    bad = queries.sales_page(RUN, ALL, None, "id; DROP TABLE sales", "asc", 1, 5)  # unknown column falls back
    assert bad["total"] == len(DF)


def test_filter_options():
    o = queries.filter_options(RUN)
    assert o["categories"] == sorted(DF.category.unique()) and o["date_min"] == "2022-01-01"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:  # report every failure, not just the first
            failed += 1
            print("FAIL", t.__name__, "->", repr(e))
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
