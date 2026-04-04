"""
routers/optimise.py
-------------------
POST /api/optimise
  Called when user clicks "Auto Optimise".
  Runs PSO + SA via M2's optimise_layout().
  After optimisation: re-runs signal + deadzone analysis so heatmap
  overlays immediately reflect new router positions.
  Returns updated router list so frontend can reposition pins instantly.
"""

from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import OptimisePayload
from app.ml_models.optimizer import optimise_layout
from app.ml_models.signal_engine     import compute_signal
from app.ml_models.deadzone_detector import detect_deadzones

router = APIRouter()


@router.post("/api/optimise")
async def run_optimise(payload: OptimisePayload):
    sid      = payload.session_id          # plain UUID string — no ObjectId needed
    db_async = get_async_db()
    db_sync  = get_sync_db()

    # ── Guard: analysis must have been run first ──────────────────────────────
    signal = await db_async["signal_results"].find_one({"session_id": sid})
    if not signal:
        raise HTTPException(
            status_code=400,
            detail="Run /api/analyse before optimising."
        )

    # ── Run PSO + SA ──────────────────────────────────────────────────────────
    # optimise_layout() now also writes new row/col back to routers collection
    try:
        result = optimise_layout(sid, db_sync)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimizer failed: {str(e)}")

    # ── Re-run signal + deadzone so heatmap refreshes immediately ─────────────
    try:
        compute_signal(sid, db_sync)
        detect_deadzones(sid, db_sync)
    except Exception as e:
        # Non-fatal — return result with a warning; user can re-click Analyse
        return {
            "status":            "ok_warn",
            "warning":           f"Optimised but re-analysis failed: {e}. "
                                  "Click Analyse to refresh the heatmap.",
            "algorithm":         result.get("algorithm",         "PSO"),
            "original_score":    result.get("original_score",    0.0),
            "optimised_score":   result.get("optimised_score",   0.0),
            "improvement_pct":   result.get("improvement_pct",   0.0),
            "optimised_routers": result.get("optimised_routers", []),
            "score_history":     result.get("score_history",     []),
            "no_change_required": result.get("no_change_required", False),
            "message":           result.get("message", ""),
            "updated_routers":   [],
        }

    # ── Fetch freshly-updated routers and return them ─────────────────────────
    # Frontend uses this list to reposition canvas pins immediately —
    # no extra GET /api/routers round-trip needed.
    updated_routers_raw = list(db_sync.routers.find({"session_id": sid}))
    updated_routers = [
        {
            "router_id":     r.get("router_id", str(r["_id"])),
            "name":          r.get("name", ""),
            "row":           r["row"],
            "col":           r["col"],
            "tx_power_dbm":  r.get("tx_power_dbm",  20),
            "frequency_mhz": r.get("frequency_mhz", 2400),
            "channel":       r.get("channel",        1),
            "range_m":       r.get("range_m",        50),
            "cost":          r.get("cost",           0),
            "is_suggested":  r.get("is_suggested",   False),
        }
        for r in updated_routers_raw
    ]

    return {
        "status":            "ok",
        "algorithm":         result.get("algorithm",         "PSO"),
        "original_score":    result.get("original_score",    0.0),
        "optimised_score":   result.get("optimised_score",   0.0),
        "improvement_pct":   result.get("improvement_pct",   0.0),
        "optimised_routers": result.get("optimised_routers", []),
        "score_history":     result.get("score_history",     []),
        "no_change_required": result.get("no_change_required", False),
        "message":           result.get("message", ""),
        "updated_routers":   updated_routers,   # ← frontend uses this to move pins
    }
