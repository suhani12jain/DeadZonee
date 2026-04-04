"""
routers/session.py
------------------
POST /api/session
  Creates a new project session from floor dimensions.
  Calculates grid_rows and grid_cols from the given dimensions.
  Writes to MongoDB 'sessions' collection.
  Returns the generated session_id.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from app.database.mongo_client import get_async_db
from app.database.schemas import SessionCreate

router = APIRouter()


@router.post("/api/session")
async def create_session(payload: SessionCreate):
    db = get_async_db()

    session_id = str(uuid.uuid4())

    grid_rows = int(payload.height_m / payload.cell_size_m)
    grid_cols = int(payload.width_m  / payload.cell_size_m)

    doc = {
        "session_id":    session_id,
        "project_name":  payload.project_name,
        "building_name": payload.building_name,
        "width_m":       payload.width_m,
        "height_m":      payload.height_m,
        "cell_size_m":   payload.cell_size_m,
        "grid_rows":     grid_rows,
        "grid_cols":     grid_cols,
        "created_at":    datetime.now(timezone.utc),
    }

    await db["sessions"].insert_one(doc)

    return {
        "session_id":  session_id,
        "grid_rows":   grid_rows,
        "grid_cols":   grid_cols,
        "cell_size_m": payload.cell_size_m,
    }
