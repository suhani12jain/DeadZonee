"""
routers/grid.py
POST /api/grid/create  — session_id (+ optional dims) → build grid → MongoDB
POST /api/grid/save-zones — update zone data per cell
GET  /api/grid/{session_id} — fetch full cell grid
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db
from app.database.schemas import GridCreatePayload, SaveZonesPayload
from app.core.grid_builder import build_grid

router = APIRouter()


# ── POST /api/grid/create ─────────────────────────────────────────────────────
@router.post("/api/grid/create")
async def create_grid(payload: GridCreatePayload):
    db = get_async_db()

    # Always fetch session for authoritative dims
    session = await db["sessions"].find_one({"session_id": payload.session_id})
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{payload.session_id}' not found")

    # Use payload dims if provided, else fall back to session dims
    width_m     = payload.width_m     if payload.width_m     is not None else session["width_m"]
    height_m    = payload.height_m    if payload.height_m    is not None else session["height_m"]
    cell_size_m = payload.cell_size_m if payload.cell_size_m is not None else session["cell_size_m"]

    if cell_size_m <= 0 or width_m <= 0 or height_m <= 0:
        raise HTTPException(status_code=422, detail="width_m, height_m, cell_size_m must all be > 0")

    grid_data = build_grid(
        width_m=width_m,
        height_m=height_m,
        cell_size_m=cell_size_m,
    )

    # Upsert — replace any existing grid for this session
    await db["grids"].delete_many({"session_id": payload.session_id})
    await db["grids"].insert_one({
        "session_id":  payload.session_id,
        "grid_rows":   grid_data["grid_rows"],
        "grid_cols":   grid_data["grid_cols"],
        "cell_size_m": cell_size_m,
        "cells":       grid_data["cells"],
    })

    return {
        "session_id":  payload.session_id,
        "grid_rows":   grid_data["grid_rows"],
        "grid_cols":   grid_data["grid_cols"],
        "cell_count":  len(grid_data["cells"]),
        "cell_size_m": cell_size_m,
        "cells":       grid_data["cells"],
    }


# ── POST /api/grid/save-zones ─────────────────────────────────────────────────
@router.post("/api/grid/save-zones")
async def save_zones(payload: SaveZonesPayload):
    db = get_async_db()

    cells_data = [c.model_dump() for c in payload.cells]

    await db["grids"].update_one(
        {"session_id": payload.session_id},
        {"$set": {"cells": cells_data}},
        upsert=True,
    )

    return {"status": "saved", "cells_saved": len(cells_data)}


# ── GET /api/grid/{session_id} ────────────────────────────────────────────────
@router.get("/api/grid/{session_id}")
async def get_grid(session_id: str):
    db = get_async_db()

    grid = await db["grids"].find_one(
        {"session_id": session_id},
        {"_id": 0},
    )
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found — run /api/grid/create first")

    return grid