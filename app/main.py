from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.db import init_db, get_asta

from app.routes_analysis import router as analysis_router
from app.routes_dashboard import router as dashboard_router
from app.routes_aste import router as aste_router

from app.ui_detail import render_asta_detail


app = FastAPI(title="Aste Suite (Local)")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(analysis_router)
app.include_router(dashboard_router)
app.include_router(aste_router)


@app.get("/aste/{asta_id}", response_class=HTMLResponse)
def detail_asta(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        raise HTTPException(status_code=404, detail="Asta non trovata")

    return HTMLResponse(content=render_asta_detail(asta))

