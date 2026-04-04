"""
routers/signal.py
-----------------
POST /api/signal
  Reads routers + zone attenuation matrix from MongoDB.
  Calls M1's compute_signal() to compute signal_matrix, quality_matrix,
  interference_matrix, and coverage metrics.
  Writes results to MongoDB 'signal_results' collection.

  NOTE: This is called internally by /api/analyse — not usually called
  directly by the frontend.
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import SessionIDPayload

# ── M1 import (swap mock → real at Hour 16) ───────────────────────────────────
from app.ml_models.signal_engine import compute_signal

router = APIRouter()


@router.post("/api/signal")
async def run_signal(payload: SessionIDPayload):
    db_async = get_async_db()
    db_sync  = get_sync_db()

    session = await db_async["sessions"].find_one({"session_id": payload.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = compute_signal(payload.session_id, db_sync)
    return {"status": "ok", "metrics": result.get("metrics", {})}
