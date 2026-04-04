"""
routers/routers_api.py
POST   /api/routers               Add a new access point
GET    /api/routers/{session_id}  Fetch all APs for a session
PUT    /api/routers/{router_id}   Update an AP
DELETE /api/routers/{router_id}   Remove an AP
"""

import uuid
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database.mongo_client import get_async_db
from app.database.schemas import RouterCreate, RouterUpdate

router = APIRouter()


# ── POST /api/routers ─────────────────────────────────────────────────────────
@router.post("/api/routers")
async def add_router(payload: RouterCreate):
    db = get_async_db()

    # Verify the target cell allows router placement
    # Search cells by row/col — never rely on index arithmetic
    grid = await db["grids"].find_one({"session_id": payload.session_id})
    if grid:
        cells = grid.get("cells", [])
        target = next(
            (c for c in cells
             if c.get("row") == payload.row and c.get("col") == payload.col),
            None,
        )
        if target is not None and not target.get("allow_router", True):
            zone = target.get("zone_type", "unknown")
            raise HTTPException(
                status_code=400,
                detail=f"Cell ({payload.row},{payload.col}) is zone '{zone}' — routers not allowed here.",
            )

    router_id = str(uuid.uuid4())
    doc = {
        "router_id":     router_id,
        "session_id":    payload.session_id,
        "name":          payload.name,
        "row":           payload.row,
        "col":           payload.col,
        "tx_power_dbm":  payload.tx_power_dbm,
        "frequency_mhz": payload.frequency_mhz,
        "channel":       payload.channel,
        "range_m":       payload.range_m,
        "cost":          payload.cost,
        "is_suggested":  payload.is_suggested,
    }

    result = await db["routers"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


# ── GET /api/routers/{session_id} ─────────────────────────────────────────────
@router.get("/api/routers/{session_id}")
async def get_routers(session_id: str):
    db = get_async_db()
    cursor  = db["routers"].find({"session_id": session_id}, {"_id": 0})
    routers = await cursor.to_list(500)
    return {"routers": routers, "count": len(routers)}


# ── PUT /api/routers/{router_id} ─────────────────────────────────────────────
@router.put("/api/routers/{router_id}")
async def update_router(router_id: str, payload: RouterUpdate):
    db = get_async_db()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db["routers"].find_one_and_update(
        {"router_id": router_id},
        {"$set": updates},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Router '{router_id}' not found")
    return result


# ── DELETE /api/routers/{router_id} ──────────────────────────────────────────
@router.delete("/api/routers/{router_id}")
async def delete_router(router_id: str):
    db = get_async_db()

    # Try string router_id first
    result = await db["routers"].delete_one({"router_id": router_id})

    # Fallback: ObjectId (older docs)
    if result.deleted_count == 0:
        try:
            result = await db["routers"].delete_one({"_id": ObjectId(router_id)})
        except Exception:
            pass

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Router '{router_id}' not found")
    return {"deleted": router_id}


# ── POST /api/routers/accept-suggestion ──────────────────────────────────────
@router.post("/api/routers/accept-suggestion")
async def accept_suggestion(body: dict):
    from app.database.mongo_client import get_sync_db
    from app.ml_models.signal_engine import compute_signal
    from app.ml_models.deadzone_detector import detect_deadzones

    db       = get_async_db()
    db_sync  = get_sync_db()
    sid      = body.get("session_id")
    sug_id   = body.get("suggestion_id")

    # FIX 1: suggestion was saved with '_id' = suggestion_id string
    suggestion = await db["suggestions"].find_one({"_id": sug_id})
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    cfg = suggestion.get("suggested_config", {})
    doc = {
        "router_id":     str(uuid.uuid4()),
        "session_id":    sid,
        "name":          f"AI-R{suggestion['suggested_row']}-C{suggestion['suggested_col']}",
        "row":           suggestion["suggested_row"],
        "col":           suggestion["suggested_col"],
        "tx_power_dbm":  cfg.get("tx_power", 20),
        "frequency_mhz": cfg.get("frequency", 2400),
        "channel":       cfg.get("channel", 6),
        "range_m":       cfg.get("range", 50),
        "cost":          2000,
        "is_suggested":  True,
    }
    result = await db["routers"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    await db["suggestions"].update_one(
        {"_id": sug_id}, {"$set": {"accepted": True}}
    )

    # FIX 2: re-run full analysis so overlays update
    try:
        compute_signal(sid, db_sync)
        detect_deadzones(sid, db_sync)
    except Exception as e:
        # Don't fail the accept if re-analyse errors — router is already saved
        print(f"[accept-suggestion] Re-analyse failed: {e}")

    return {"status": "accepted", **doc}