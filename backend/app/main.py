"""
main.py
-------
FastAPI application entry point for DeadZero v3.0.

Registers all routers.
Sets CORS to allow the Vite frontend (localhost:5173) and any
deployed Vercel domain.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    session,
    grid,
    routers_api,
    signal,
    deadzones,
    analyse,
    optimise,
    suggest,
    report,
    rf_explain,
    what_if,
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "DeadZero API",
    description = "Smart Wireless Infrastructure Planning — v3.0",
    version     = "3.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://localhost:3000",    # alternate dev port
        "https://*.vercel.app",     # Vercel deploy
        "*",                        # open during hackathon — restrict before production
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(session.router)       # POST /api/session
app.include_router(grid.router)          # POST /api/grid/create | POST /api/grid/save-zones | GET /api/grid/{id}
app.include_router(routers_api.router)   # POST/GET/DELETE /api/routers
app.include_router(signal.router)        # POST /api/signal
app.include_router(deadzones.router)     # POST /api/deadzones
app.include_router(analyse.router)       # POST /api/analyse | GET /api/results/{id}
app.include_router(optimise.router)      # POST /api/optimise
app.include_router(suggest.router)       # POST /api/suggest | POST /api/routers/accept-suggestion
app.include_router(report.router)        # GET  /api/report
app.include_router(rf_explain.router)    # GET  /api/explain/{id}
app.include_router(what_if.router)       # POST /api/what-if


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "DeadZero API",
        "version": "3.0.0",
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health")
async def health():
    from app.database.mongo_client import get_async_db
    db = get_async_db()
    try:
        await db.list_collection_names()
        mongo_status = "connected"
    except Exception as e:
        mongo_status = f"error: {str(e)}"
    return {"status": "ok", "mongodb": mongo_status}
