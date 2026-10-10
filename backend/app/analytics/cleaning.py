"""
Data cleaning for SalesCast.

clean_sales() takes the raw DataFrame and returns (clean_df, report).
Rows are only dropped for a documented reason, and every step is counted
so the data-quality summary reflects what actually happened.
"""
import pandas as pd

REQUIRED = ["order_id", "order_date", "product", "category", "region",
            "quantity", "unit_price", "discount", "sales"]
OPTIONAL = ["profit"]
TEXT_COLS = ["order_id", "product", "category", "region"]
NUMERIC_COLS = ["quantity", "unit_price", "discount", "sales", "profit"]


def clean_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    missing_cols = [c for c in REQUIRED if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {missing_cols}")
    df = df[REQUIRED + [c for c in OPTIONAL if c in df.columns]].copy()

    transformations: list[str] = []
    removed: dict[str, int] = {}

    report = {
        "records_raw": int(len(df)),
        "missing_values_by_column": {c: int(n) for c, n in df.isna().sum().items() if n},
        "missing_values_total": int(df.isna().sum().sum()),
    }

    # --- 1. Fix data types -------------------------------------------------
    for c in TEXT_COLS:
        df[c] = df[c].astype("string").str.strip()
        df.loc[df[c] == "", c] = pd.NA
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    for c in [c for c in NUMERIC_COLS if c in df.columns]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    transformations.append("Trimmed text columns; parsed order_date as date; coerced numeric columns (unparseable values become missing).")

    def drop(mask: pd.Series, reason: str):
        nonlocal df
        removed[reason] = int(mask.sum())
        df = df[~mask]

    # --- 2. Remove invalid rows (sequential, so each count is exclusive) ---
    drop(df["order_date"].isna(), "invalid_dates")
    drop(df["order_id"].isna(), "missing_order_id")
    drop(df[["product", "category", "region"]].isna().any(axis=1), "missing_product_category_or_region")
    drop(df.duplicated("order_id", keep="first"), "duplicate_orders")
    drop(df["quantity"].isna() | (df["quantity"] <= 0), "invalid_quantities")
    drop(df["unit_price"].isna() | (df["unit_price"] <= 0), "invalid_prices")
    drop(df["sales"].isna() | (df["sales"] < 0), "negative_or_missing_sales")
    drop(df["discount"].notna() & ((df["discount"] < 0) | (df["discount"] > 1)), "invalid_discounts")
    transformations.append("Dropped rows with invalid dates, missing identifiers, duplicate order_id (first kept), non-positive quantity/price, or negative sales.")

    # --- 3. Repair missing discounts from the order's own numbers ----------
    # sales = quantity * unit_price * (1 - discount)  =>  discount = 1 - sales / (quantity * unit_price)
    needs_discount = df["discount"].isna()
    derived = (1 - df["sales"] / (df["quantity"] * df["unit_price"])).round(2).clip(0, 1)
    df.loc[needs_discount, "discount"] = derived[needs_discount]
    report["discounts_recovered"] = int(needs_discount.sum())
    if needs_discount.any():
        transformations.append("Recovered missing discounts as 1 - sales / (quantity * unit_price), rounded to 2 decimals.")

    # --- 4. Consistency check (reported, not dropped) ----------------------
    expected = df["quantity"] * df["unit_price"] * (1 - df["discount"])
    report["sales_formula_mismatches"] = int(((df["sales"] - expected).abs() > 0.02).sum())

    # --- 5. Final types ----------------------------------------------------
    df["quantity"] = df["quantity"].astype(int)
    for c in TEXT_COLS:
        df[c] = df[c].astype(str)
    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)

    report.update({
        "records_clean": int(len(df)),
        "records_removed": int(report["records_raw"] - len(df)),
        "removed_by_reason": removed,
        "invalid_dates": removed["invalid_dates"],
        "duplicate_orders": removed["duplicate_orders"],
        "date_range": [df["order_date"].min().strftime("%Y-%m-%d"),
                       df["order_date"].max().strftime("%Y-%m-%d")],
        "has_profit": "profit" in df.columns and bool(df["profit"].notna().any()),
        "transformations": transformations,
    })
    return df, report
