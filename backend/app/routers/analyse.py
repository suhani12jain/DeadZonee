"""
routers/analyse.py
------------------
POST /api/analyse
  Main analysis orchestrator. Called when the user clicks "Analyse" in the UI.
  Runs the full pipeline sequentially:
    1. compute_signal()    — M1: builds signal_matrix from zone attenuation + routers
    2. detect_deadzones()  — M1: finds dead zone clusters from signal_matrix

  All intermediate results are written to MongoDB by each ML function.
  Returns 'done' when all steps complete, or an error message with the failing step.

GET /api/results/{session_id}
  Returns all result matrices for frontend overlay rendering.
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import AnalysePayload

# ── M1 imports (swap mock → real at Hour 16) ──────────────────────────────────
from app.ml_models.signal_engine    import compute_signal
from app.ml_models.deadzone_detector import detect_deadzones

router = APIRouter()


# ── POST /api/analyse ─────────────────────────────────────────────────────────
@router.post("/api/analyse")
async def run_analysis(payload: AnalysePayload):
    db_async = get_async_db()
    db_sync  = get_sync_db()

    session = await db_async["sessions"].find_one({"session_id": payload.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sid = payload.session_id

    # ── Step 1: Signal Engine ─────────────────────────────────────────────────
    try:
        sig_result = compute_signal(sid, db_sync)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal engine failed: {str(e)}")

    # ── Step 2: Dead Zone Detector ────────────────────────────────────────────
    try:
        dz_result = detect_deadzones(sid, db_sync)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dead zone detection failed: {str(e)}")

    return {
        "status":          "done",
        "session_id":      sid,
        "metrics":         sig_result.get("metrics", {}),
        "dead_zone_count": dz_result.get("dead_zone_count", 0),
        "cluster_count":   len(dz_result.get("clusters", [])),
    }


# ── GET /api/results/{session_id} ─────────────────────────────────────────────
@router.get("/api/results/{session_id}")
async def get_results(session_id: str):
    db = get_async_db()

    signal   = await db["signal_results"].find_one({"session_id": session_id}, {"_id": 0})
    deadzones = await db["deadzones"].find_one({"session_id": session_id},     {"_id": 0})

    if not signal:
        raise HTTPException(status_code=404, detail="No analysis results found. Run /api/analyse first.")

    return {
        # Signal matrices
        "signal_matrix":       signal.get("signal_matrix",       []),
        "quality_matrix":      signal.get("quality_matrix",      []),
        "interference_matrix": signal.get("interference_matrix", []),
        "metrics":             signal.get("metrics",             {}),

        # Dead zone data
        "dead_zone_mask":  deadzones.get("dead_zone_mask",  []) if deadzones else [],
        "dead_zone_count": deadzones.get("dead_zone_count", 0)  if deadzones else 0,
        "clusters":        deadzones.get("clusters",        []) if deadzones else [],
    }
