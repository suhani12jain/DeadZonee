"""
routers/optimise.py
-------------------
POST /api/optimise
  Called when user clicks "Auto Optimise".
  Calls M2's optimise_layout() which runs PSO + Simulated Annealing.
  Reads: signal_results, deadzones, grids, routers from MongoDB.
  Writes: optimisation_results to MongoDB.
  Returns: score before/after, winning algorithm, new router positions, score_history.
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import OptimisePayload

# ── M2 import (swap mock → real at Hour 16) ───────────────────────────────────
from app.ml_models.optimizer import optimise_layout

router = APIRouter()


@router.post("/api/optimise")
async def run_optimise(payload: OptimisePayload):
    db_async = get_async_db()
    db_sync  = get_sync_db()

    # Ensure analysis has been run first
    signal = await db_async["signal_results"].find_one({"session_id": payload.session_id})
    if not signal:
        raise HTTPException(
            status_code=400,
            detail="Run /api/analyse before optimising."
        )

    try:
        result = optimise_layout(payload.session_id, db_sync)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimizer failed: {str(e)}")

    return {
        "status":             "ok",
        "algorithm":          result.get("algorithm",          "PSO"),
        "original_score":     result.get("original_score",     0.0),
        "optimised_score":    result.get("optimised_score",    0.0),
        "improvement_pct":    result.get("improvement_pct",    0.0),
        "optimised_routers":  result.get("optimised_routers",  []),
        "score_history":      result.get("score_history",      []),
    }