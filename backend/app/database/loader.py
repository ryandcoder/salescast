import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.analytics.cleaning import clean_sales

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DATA_PATH = Path(os.getenv("DATA_PATH", "/data/sales.csv"))
REPORT_PATH = Path(os.getenv("REPORT_PATH", "/data/data_quality_report.json"))


def init_database(engine: Engine) -> None:
    """Create the schema, then load cleaned data if the table is empty."""
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_PATH.read_text())
        count = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()

    if count > 0:
        print(f"[loader] sales table already has {count:,} rows; skipping load.")
        return

    print(f"[loader] reading {DATA_PATH}")
    clean, report = clean_sales(pd.read_csv(DATA_PATH))
    clean["order_date"] = clean["order_date"].dt.date
    clean.to_sql("sales", engine, if_exists="append", index=False,
                 chunksize=2000, method="multi")

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"[loader] loaded {len(clean):,} rows "
          f"({report['records_removed']} removed during cleaning).")
