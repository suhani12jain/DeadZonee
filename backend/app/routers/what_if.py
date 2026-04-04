"""
POST /api/what-if
  Simulates zone edits in memory only. Never writes grids or signal_results.
"""

import os
from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db
from app.database.schemas import WhatIfPayload
from app.ml_models.what_if_agent import run_what_if

router = APIRouter()


def _normalize_manual(entries):
    out = []
    for m in entries or []:
        d = m.model_dump(exclude_none=True)
        z = d.get("zone_type")
        if not z:
            raise HTTPException(status_code=422, detail="Each manual change needs zone_type")
        if d.get("row") is not None and d.get("col") is not None:
            out.append({
                "row": int(d["row"]),
                "col": int(d["col"]),
                "zone_type": z,
            })
            continue
        keys = ("row_min", "row_max", "col_min", "col_max")
        if all(k in d for k in keys):
            out.append({
                "row_min": int(d["row_min"]),
                "row_max": int(d["row_max"]),
                "col_min": int(d["col_min"]),
                "col_max": int(d["col_max"]),
                "zone_type": z,
            })
            continue
        raise HTTPException(
            status_code=422,
            detail="manual_changes need either (row,col) or (row_min,row_max,col_min,col_max)",
        )
    return out


@router.post("/api/what-if")
async def what_if_simulate(payload: WhatIfPayload):
    db = get_async_db()

    session = await db["sessions"].find_one({"session_id": payload.session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    grid = await db["grids"].find_one({"session_id": payload.session_id}, {"_id": 0})
    if not grid or not grid.get("cells"):
        raise HTTPException(status_code=404, detail="Grid not found")

    routers = await db["routers"].find({"session_id": payload.session_id}, {"_id": 0}).to_list(200)
    if not routers:
        raise HTTPException(
            status_code=400,
            detail="Place at least one router before running a what-if simulation.",
        )

    q = (payload.query or "").strip()
    manual = _normalize_manual(payload.manual_changes)

    if not q and not manual:
        raise HTTPException(
            status_code=422,
            detail="Send a natural-language query and/or manual_changes.",
        )

    try:
        result = run_what_if(
            session=session,
            grid_doc=grid,
            routers=routers,
            query=q if q else None,
            manual_changes=manual if manual else None,
            anthropic_key=os.getenv("ANTHROPIC_KEY", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"What-if failed: {e}")

    return {"status": "ok", **result}
