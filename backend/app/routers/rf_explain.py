import os

from fastapi import APIRouter, HTTPException

from app.database.mongo_client import get_async_db
from app.ml_models.rf_explainer import build_rf_explanations

router = APIRouter()


@router.get("/api/explain/{session_id}")
async def get_rf_explanations(session_id: str):
    db = get_async_db()

    session_doc = await db["sessions"].find_one({"session_id": session_id}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    grid_doc = await db["grids"].find_one({"session_id": session_id}, {"_id": 0})
    signal_doc = await db["signal_results"].find_one({"session_id": session_id}, {"_id": 0})
    deadzones_doc = await db["deadzones"].find_one({"session_id": session_id}, {"_id": 0})
    routers = await db["routers"].find({"session_id": session_id}, {"_id": 0}).to_list(200)

    if not signal_doc:
        raise HTTPException(status_code=404, detail="No analysis results found. Run /api/analyse first.")

    try:
        explanations = build_rf_explanations(
            session_doc,
            grid_doc,
            signal_doc,
            deadzones_doc,
            routers,
            anthropic_key=os.getenv("ANTHROPIC_KEY", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RF explainer failed: {exc}")

    return {
        "session_id": session_id,
        "rf_explanations": explanations,
    }
