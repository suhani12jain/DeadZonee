"""
routers/deadzones.py
--------------------
POST /api/deadzones
  Reads signal_matrix from MongoDB 'signal_results'.
  Calls M1's detect_deadzones() which applies a NumPy threshold mask
  and SciPy ndimage.label() to find connected dead zone clusters.
  Writes results to MongoDB 'deadzones' collection.

  NOTE: Called internally by /api/analyse.
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import SessionIDPayload

# ── M1 import ─────────────────────────────────────────────────────────────────
from app.ml_models.deadzone_detector import detect_deadzones

router = APIRouter()


@router.post("/api/deadzones")
async def run_deadzones(payload: SessionIDPayload):
    db_async = get_async_db()
    db_sync  = get_sync_db()

    # Ensure signal results exist before running
    signal = await db_async["signal_results"].find_one({"session_id": payload.session_id})
    if not signal:
        raise HTTPException(
            status_code=400,
            detail="Signal analysis must run before dead zone detection."
        )

    result = detect_deadzones(payload.session_id, db_sync)
    return {
        "status":          "ok",
        "dead_zone_count": result.get("dead_zone_count", 0),
        "cluster_count":   len(result.get("clusters", [])),
    }
