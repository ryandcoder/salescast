"""
SQL access layer for SalesCast.

All aggregation that can be done in SQL is done in SQL. Functions take a
`run(sql, params) -> list[dict]` callable instead of a database connection,
which keeps this module independent of SQLAlchemy and easy to test.
Only portable SQL is used (no PostgreSQL-only functions).
"""
from dataclasses import asdict, dataclass
from datetime import date
from typing import Callable, Optional

import pandas as pd

Run = Callable[[str, Optional[dict]], list]

SORTABLE_SALES = {"order_id", "order_date", "product", "category", "region",
                  "quantity", "unit_price", "discount", "sales"}


@dataclass(frozen=True)
class Filters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    category: Optional[str] = None
    product: Optional[str] = None
    region: Optional[str] = None

    def is_filtered(self) -> bool:
        return any(v is not None for v in asdict(self).values())

    def as_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, date) else v)
                for k, v in asdict(self).items() if v is not None}


def build_where(f: Filters, extra: tuple = ()) -> tuple[str, dict]:
    clauses, params = list(extra), {}
    if f.date_from:
        clauses.append("order_date >= :date_from")
        params["date_from"] = f.date_from
    if f.date_to:
        clauses.append("order_date <= :date_to")
        params["date_to"] = f.date_to
    for col in ("category", "product", "region"):
        value = getattr(f, col)
        if value:
            clauses.append(f"{col} = :{col}")
            params[col] = value
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _r(x, nd: int = 2):
    if x is None or pd.isna(x):
        return None
    return round(float(x), nd)


def _day(x) -> Optional[str]:
    return None if x is None else str(x)[:10]


# --------------------------------------------------------------------------
def filter_options(run: Run) -> dict:
    prods = run("SELECT product, MIN(category) AS category FROM sales GROUP BY product ORDER BY product", {})
    cats = run("SELECT DISTINCT category FROM sales ORDER BY category", {})
    regs = run("SELECT DISTINCT region FROM sales ORDER BY region", {})
    span = run("SELECT MIN(order_date) AS d0, MAX(order_date) AS d1 FROM sales", {})[0]
    return {"categories": [r["category"] for r in cats],
            "regions": [r["region"] for r in regs],
            "products": [{"product": r["product"], "category": r["category"]} for r in prods],
            "date_min": _day(span["d0"]), "date_max": _day(span["d1"])}


def kpis(run: Run, f: Filters) -> dict:
    where, params = build_where(f)
    row = run(f"""
        SELECT CAST(COALESCE(SUM(sales), 0) AS FLOAT) AS revenue,
               COUNT(DISTINCT order_id)               AS orders,
               COALESCE(SUM(quantity), 0)             AS units,
               CAST(SUM(profit) AS FLOAT)             AS profit,
               COUNT(profit)                          AS profit_rows,
               MIN(order_date) AS first_date, MAX(order_date) AS last_date
        FROM sales{where}""", params)[0]

    revenue, orders, units = row["revenue"], int(row["orders"]), int(row["units"])
    months = 0
    if row["first_date"] is not None:
        a, b = pd.Timestamp(row["first_date"]), pd.Timestamp(row["last_date"])
        months = (b.year - a.year) * 12 + (b.month - a.month) + 1

    products = grouped(run, f, "product")
    regions = grouped(run, f, "region")
    by_units = max(products, key=lambda p: p["units"], default=None)

    def pick(item, *keys):
        return None if item is None else {k: item[k] for k in keys}

    profit = None
    if row["profit_rows"]:
        profit = {"total_profit": _r(row["profit"]),
                  "profit_margin_pct": _r(row["profit"] / revenue * 100) if revenue else None}

    return {
        "total_revenue": _r(revenue),
        "total_orders": orders,
        "units_sold": units,
        "average_order_value": _r(revenue / orders) if orders else None,
        "average_monthly_revenue": _r(revenue / months) if months else None,
        "months_covered": months,
        "best_product_by_revenue": pick(products[0] if products else None, "name", "revenue", "units"),
        "best_product_by_units": pick(by_units, "name", "revenue", "units"),
        "best_region": pick(regions[0] if regions else None, "name", "revenue", "orders"),
        "profit": profit,
        "data_range": [_day(row["first_date"]), _day(row["last_date"])],
    }


def grouped(run: Run, f: Filters, key: str) -> list[dict]:
    """Revenue/units/orders/profit per category, product or region (highest revenue first)."""
    if key not in {"category", "product", "region"}:
        raise ValueError(key)
    where, params = build_where(f)
    extra = ", MIN(category) AS category" if key == "product" else ""
    rows = run(f"""
        SELECT {key} AS name{extra},
               CAST(SUM(sales) AS FLOAT)      AS revenue,
               SUM(quantity)                  AS units,
               COUNT(DISTINCT order_id)       AS orders,
               CAST(AVG(unit_price) AS FLOAT) AS avg_price,
               CAST(SUM(profit) AS FLOAT)     AS profit
        FROM sales{where}
        GROUP BY {key}
        ORDER BY revenue DESC""", params)

    total = sum(r["revenue"] for r in rows)
    out = []
    for r in rows:
        item = {"name": r["name"], "revenue": _r(r["revenue"]), "units": int(r["units"]),
                "orders": int(r["orders"]), "avg_price": _r(r["avg_price"]),
                "average_order_value": _r(r["revenue"] / r["orders"]) if r["orders"] else None,
                "pct_of_revenue": _r(r["revenue"] / total * 100) if total else 0.0,
                "profit": _r(r["profit"]),
                "profit_margin_pct": _r(r["profit"] / r["revenue"] * 100) if r["profit"] is not None and r["revenue"] else None}
        if key == "product":
            item["category"] = r["category"]
        out.append(item)
    return out


def daily_series(run: Run, f: Filters) -> list[dict]:
    """One row per day with sales; month/quarter/year views are built from this in pandas."""
    where, params = build_where(f)
    return run(f"""
        SELECT order_date,
               CAST(SUM(sales) AS FLOAT)  AS revenue,
               SUM(quantity)              AS units,
               COUNT(DISTINCT order_id)   AS orders,
               CAST(SUM(profit) AS FLOAT) AS profit
        FROM sales{where}
        GROUP BY order_date
        ORDER BY order_date""", params)


def sales_page(run: Run, f: Filters, q: Optional[str], sort_by: str, order: str,
               page: int, page_size: int) -> dict:
    sort_col = sort_by if sort_by in SORTABLE_SALES else "order_date"
    direction = "ASC" if order.lower() == "asc" else "DESC"
    extra, search = (), {}
    if q and q.strip():
        extra = ("(LOWER(order_id) LIKE :q OR LOWER(product) LIKE :q "
                 "OR LOWER(category) LIKE :q OR LOWER(region) LIKE :q)",)
        search["q"] = f"%{q.strip().lower()}%"
    where, params = build_where(f, extra)
    params.update(search)

    total = run(f"SELECT COUNT(*) AS n FROM sales{where}", params)[0]["n"]
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = run(f"""
        SELECT order_id, order_date, product, category, region, quantity,
               CAST(unit_price AS FLOAT) AS unit_price,
               CAST(discount AS FLOAT)   AS discount,
               CAST(sales AS FLOAT)      AS sales
        FROM sales{where}
        ORDER BY {sort_col} {direction}, order_id ASC
        LIMIT :limit OFFSET :offset""", params)
    for r in rows:
        r["order_date"] = _day(r["order_date"])
    return {"total": int(total), "page": page, "page_size": page_size, "items": rows}
