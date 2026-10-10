from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from app.analytics import queries, trends
from app.analytics.queries import Filters
from app.forecasting import insights as insights_mod
from app.forecasting import model as forecast_model

router = APIRouter(prefix="/api")

# The dataset is loaded once at startup and never changes while the app runs, so a fitted
# forecast for a given (filters, horizon) can be reused by /forecast, /forecast/accuracy and /insights.
_FORECAST_CACHE: dict = {}
_CACHE_LIMIT = 64


def _forecast(run, f: Filters, horizon: int) -> dict:
    if horizon not in forecast_model.HORIZONS:
        raise HTTPException(422, f"horizon must be one of {list(forecast_model.HORIZONS)} months.")
    key = (f, horizon)
    if key not in _FORECAST_CACHE:
        if len(_FORECAST_CACHE) >= _CACHE_LIMIT:
            _FORECAST_CACHE.clear()
        _FORECAST_CACHE[key] = forecast_model.build_forecast(queries.daily_series(run, f), f, horizon)
    return _FORECAST_CACHE[key]


def get_run(request: Request):
    """One database connection per request, exposed as run(sql, params) -> list[dict]."""
    with request.app.state.engine.connect() as conn:
        def run(sql: str, params: Optional[dict] = None) -> list:
            return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]
        yield run


def get_filters(date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
                category: Optional[str] = Query(None), product: Optional[str] = Query(None),
                region: Optional[str] = Query(None)) -> Filters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to.")
    return Filters(date_from, date_to, category or None, product or None, region or None)


@router.get("/filters")
def filters(run=Depends(get_run)):
    """Values for the filter dropdowns and the full date range of the data."""
    return queries.filter_options(run)


@router.get("/dashboard")
def dashboard(f: Filters = Depends(get_filters), run=Depends(get_run)):
    return {"scope": {"is_filtered": f.is_filtered(), "filters": f.as_dict()},
            "kpis": queries.kpis(run, f)}


@router.get("/categories")
def categories(f: Filters = Depends(get_filters), run=Depends(get_run)):
    return {"items": queries.grouped(run, f, "category")}


@router.get("/regions")
def regions(f: Filters = Depends(get_filters), run=Depends(get_run)):
    return {"items": queries.grouped(run, f, "region")}


@router.get("/products")
def products(sort_by: str = Query("revenue", pattern="^(name|revenue|units|avg_price|orders|profit|profit_margin_pct)$"),
             order: str = Query("desc", pattern="^(asc|desc)$"),
             top_n: int = Query(5, ge=1, le=20),
             f: Filters = Depends(get_filters), run=Depends(get_run)):
    rows = queries.grouped(run, f, "product")
    items = sorted(rows, key=lambda r: (r[sort_by] is None, r[sort_by]), reverse=(order == "desc"))
    has_profit = any(r["profit"] is not None for r in rows)
    return {
        "items": items,
        "top_by_revenue": sorted(rows, key=lambda r: r["revenue"], reverse=True)[:top_n],
        "top_by_units": sorted(rows, key=lambda r: r["units"], reverse=True)[:top_n],
        "top_by_profit": (sorted([r for r in rows if r["profit"] is not None],
                                 key=lambda r: r["profit"], reverse=True)[:top_n] if has_profit else []),
        "lowest_by_revenue": sorted(rows, key=lambda r: r["revenue"])[:top_n],
    }


@router.get("/trends")
def trends_endpoint(granularity: str = Query("month", pattern="^(month|quarter|year)$"),
                    f: Filters = Depends(get_filters), run=Depends(get_run)):
    payload = trends.build_trends(queries.daily_series(run, f), f, granularity)
    payload["scope"] = {"is_filtered": f.is_filtered(), "filters": f.as_dict()}
    return payload


@router.get("/sales")
def sales(q: Optional[str] = Query(None, max_length=100),
          sort_by: str = Query("order_date"), order: str = Query("desc", pattern="^(asc|desc)$"),
          page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
          f: Filters = Depends(get_filters), run=Depends(get_run)):
    return queries.sales_page(run, f, q, sort_by, order, page, page_size)


@router.get("/forecast")
def forecast(horizon: int = Query(forecast_model.DEFAULT_HORIZON),
             f: Filters = Depends(get_filters), run=Depends(get_run)):
    """Monthly revenue forecast (3, 6 or 12 months) with prediction intervals, labeled overall or filtered."""
    payload = _forecast(run, f, horizon)
    return {k: v for k, v in payload.items() if k != "accuracy"}


@router.get("/forecast/accuracy")
def forecast_accuracy(horizon: int = Query(forecast_model.DEFAULT_HORIZON),
                      f: Filters = Depends(get_filters), run=Depends(get_run)):
    """Holdout evaluation: Holt-Winters vs naive baselines (MAE, RMSE, MAPE) on unseen months."""
    payload = _forecast(run, f, horizon)
    return {"scope": payload["scope"], "available": payload["available"],
            "model": payload.get("model"), "accuracy": payload["accuracy"]}


@router.get("/insights")
def insights(horizon: int = Query(forecast_model.DEFAULT_HORIZON),
             f: Filters = Depends(get_filters), run=Depends(get_run)):
    """Key insights, recommendations and inventory signal, all computed from the data and forecast."""
    fc = _forecast(run, f, horizon)
    tr = trends.build_trends(queries.daily_series(run, f), f, "month")
    return insights_mod.build_insights(run, f, fc, tr)
