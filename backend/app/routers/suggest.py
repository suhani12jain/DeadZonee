"""
routers/suggest.py
------------------
POST /api/suggest
  Called when user clicks "AI Investigator".
  Calls M2's suggest_placement() which:
    - Finds highest-priority dead zone cluster
    - Identifies best cell for a new router
    - Calls Anthropic Claude API for natural language explanation
  Writes to MongoDB 'suggestions' collection.
  Returns: suggested_row, suggested_col, config, explanation, coverage_gain_pct.

POST /api/routers/accept-suggestion
  Marks the suggestion as accepted in MongoDB.
  Adds the suggested router to the 'routers' collection.
  Triggers a full re-analysis automatically.
"""
"""
routers/suggest.py
------------------
POST /api/suggest  — AI router placement suggestion
"""

import os
from fastapi import APIRouter, HTTPException
from app.database.mongo_client import get_async_db, get_sync_db
from app.database.schemas import SuggestPayload
from app.ml_models.placement_suggester import suggest_placement

router = APIRouter()


@router.post("/api/suggest")
async def run_suggest(payload: SuggestPayload):
    db_async = get_async_db()
    db_sync  = get_sync_db()

    dz = await db_async["deadzones"].find_one({"session_id": payload.session_id})
    if not dz or not dz.get("clusters"):
        raise HTTPException(
            status_code=400,
            detail="No dead zone clusters found. Run /api/analyse first."
        )

    anthropic_key = os.getenv("ANTHROPIC_KEY", "")

    try:
        result = suggest_placement(payload.session_id, db_sync, anthropic_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI suggester failed: {str(e)}")

    return {
        "status":            "ok",
        "suggestion_id":     str(result.get("_id", "")),
        "suggested_row":     result.get("suggested_row"),
        "suggested_col":     result.get("suggested_col"),
        "suggested_config":  result.get("suggested_config", {}),
        "explanation":       result.get("explanation", ""),
        "coverage_gain_pct": result.get("coverage_gain_pct", 0.0),
    }