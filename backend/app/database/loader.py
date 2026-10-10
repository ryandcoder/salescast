import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.analytics.cleaning import clean_sales

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
# Defaults to <repo>/data (in the Docker image that resolves to /data, which compose mounts).
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_PATH = Path(os.getenv("DATA_PATH", _DATA_DIR / "sales.csv"))
REPORT_PATH = Path(os.getenv("REPORT_PATH", _DATA_DIR / "data_quality_report.json"))


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

    try:
        REPORT_PATH.write_text(json.dumps(report, indent=2))
    except OSError as exc:  # read-only or temporary disk: the API rebuilds the report on request
        print(f"[loader] could not save the data-quality report ({exc}); it will be rebuilt on demand.")
    print(f"[loader] loaded {len(clean):,} rows "
          f"({report['records_removed']} removed during cleaning).")
