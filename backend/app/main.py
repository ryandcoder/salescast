import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sqlalchemy import text

from app.analytics.cleaning import clean_sales
from app.api.routes import router
from app.database.connection import get_engine
from app.database.loader import DATA_PATH, REPORT_PATH, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = get_engine()
    init_database(app.state.engine)
    yield


app = FastAPI(title="SalesCast API", lifespan=lifespan)
# Browsers on another origin (the Vercel site) may only call the API if it is listed here.
# CORS_ORIGINS is a comma-separated list; CORS_ORIGIN_REGEX optionally allows Vercel preview URLs.
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in
                   os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
                   allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/health")
def health():
    with app.state.engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
    return {"status": "ok", "sales_rows": rows}


@app.get("/api/data-quality")
def data_quality():
    """Cleaning summary written when the dataset was first loaded."""
    if REPORT_PATH.exists():
        return json.loads(REPORT_PATH.read_text())
    # Hosts with a temporary disk lose the saved file on restart while the database survives,
    # so rebuild the same summary from the source CSV.
    if not DATA_PATH.exists():
        raise HTTPException(404, "No data-quality report found.")
    _, report = clean_sales(pd.read_csv(DATA_PATH))
    return report


app.include_router(router)
