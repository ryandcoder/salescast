import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.database.connection import get_engine
from app.database.loader import REPORT_PATH, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = get_engine()
    init_database(app.state.engine)
    yield


app = FastAPI(title="SalesCast API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/health")
def health():
    with app.state.engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
    return {"status": "ok", "sales_rows": rows}


@app.get("/api/data-quality")
def data_quality():
    """Cleaning summary written when the dataset was first loaded."""
    if not REPORT_PATH.exists():
        raise HTTPException(404, "No data-quality report found.")
    return json.loads(REPORT_PATH.read_text())


app.include_router(router)
