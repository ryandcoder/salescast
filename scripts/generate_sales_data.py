"""
Generate a SYNTHETIC retail sales dataset for SalesCast.

This data is artificially generated (seeded, reproducible). It is NOT real
company data and must not be presented as such. It includes a mild upward
trend, a yearly seasonal pattern (Nov/Dec peak, Jan/Feb dip), random noise,
and a small number of deliberate data-quality issues so the cleaning step
has something real to find.

Usage:  python scripts/generate_sales_data.py
Output: data/sales.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = "2022-01-01", "2025-12-31"
BASE_ORDERS_PER_MONTH = 330
ANNUAL_GROWTH = 0.08

# month -> seasonal multiplier (peaks in Nov/Dec, dip in Jan/Feb)
SEASONALITY = {1: 0.80, 2: 0.82, 3: 0.95, 4: 0.97, 5: 1.00, 6: 1.02,
               7: 0.98, 8: 1.03, 9: 1.08, 10: 1.05, 11: 1.30, 12: 1.45}

# category -> (share of orders, cost ratio of price)
CATEGORIES = {"Technology": (0.28, 0.72), "Furniture": (0.27, 0.68),
              "Office Supplies": (0.45, 0.60)}

# product -> (category, typical unit price)
PRODUCTS = {
    "Laptop": ("Technology", 850), "Monitor": ("Technology", 260),
    "Wireless Mouse": ("Technology", 28), "Mechanical Keyboard": ("Technology", 95),
    "Webcam": ("Technology", 70), "Headset": ("Technology", 85),
    "External SSD": ("Technology", 120), "Printer": ("Technology", 210),
    "Office Chair": ("Furniture", 230), "Standing Desk": ("Furniture", 480),
    "Bookcase": ("Furniture", 150), "Filing Cabinet": ("Furniture", 175),
    "Desk Lamp": ("Furniture", 45), "Conference Table": ("Furniture", 720),
    "Sofa": ("Furniture", 650), "Notebook Pack": ("Office Supplies", 12),
    "Pen Set": ("Office Supplies", 9), "Printer Paper": ("Office Supplies", 24),
    "Stapler": ("Office Supplies", 15), "Binder Set": ("Office Supplies", 18),
    "Whiteboard": ("Office Supplies", 60), "Marker Pack": ("Office Supplies", 11),
    "Sticky Notes": ("Office Supplies", 7), "Ink Cartridge": ("Office Supplies", 48),
}

REGIONS = {"West": 0.31, "East": 0.29, "Central": 0.22, "South": 0.18}
DISCOUNTS = [0.0, 0.05, 0.10, 0.20, 0.30]
DISCOUNT_P = [0.55, 0.15, 0.15, 0.10, 0.05]


def main():
    rng = np.random.default_rng(SEED)
    months = pd.period_range(START, END, freq="M")
    cat_names = list(CATEGORIES)
    cat_p = [CATEGORIES[c][0] for c in cat_names]
    prod_by_cat = {c: [p for p, (pc, _) in PRODUCTS.items() if pc == c] for c in cat_names}

    rows = []
    for i, period in enumerate(months):
        growth = (1 + ANNUAL_GROWTH) ** (i / 12)
        expected = BASE_ORDERS_PER_MONTH * growth * SEASONALITY[period.month]
        n = max(50, int(rng.normal(expected, expected * 0.06)))
        days = period.days_in_month
        for _ in range(n):
            cat = rng.choice(cat_names, p=cat_p)
            product = rng.choice(prod_by_cat[cat])
            base_price = PRODUCTS[product][1]
            unit_price = round(base_price * rng.uniform(0.92, 1.08), 2)
            max_q = 3 if cat != "Office Supplies" else 10
            qty = int(rng.integers(1, max_q + 1))
            disc = float(rng.choice(DISCOUNTS, p=DISCOUNT_P))
            sales = round(qty * unit_price * (1 - disc), 2)
            cost = round(qty * unit_price * CATEGORIES[cat][1] * rng.uniform(0.95, 1.05), 2)
            rows.append({
                "order_date": period.to_timestamp() + pd.Timedelta(days=int(rng.integers(0, days))),
                "product": product, "category": cat,
                "region": rng.choice(list(REGIONS), p=list(REGIONS.values())),
                "quantity": qty, "unit_price": unit_price, "discount": disc,
                "sales": sales, "profit": round(sales - cost, 2),
            })

    df = pd.DataFrame(rows).sort_values("order_date").reset_index(drop=True)
    df.insert(0, "order_id", [f"ORD-{d:%Y}-{i + 1:06d}" for i, d in enumerate(df["order_date"])])
    df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")

    # Deliberate, documented data-quality issues (for the cleaning step)
    dup = df.sample(15, random_state=SEED)
    df = pd.concat([df, dup], ignore_index=True).sort_values("order_id").reset_index(drop=True)
    df.loc[df.sample(10, random_state=SEED + 1).index, "discount"] = np.nan

    out = Path(__file__).resolve().parent.parent / "data" / "sales.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} rows to {out}")


if __name__ == "__main__":
    main()
