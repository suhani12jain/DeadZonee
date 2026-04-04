"""
routers/report.py
-----------------
GET /api/report?session_id={id}
  Reads all MongoDB collections for the session.
  Calls report_builder.py to generate a ReportLab PDF.
  Returns the PDF as a StreamingResponse for browser download.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.database.mongo_client import get_async_db
from app.utils.report_builder import build_pdf

router = APIRouter()


@router.get("/api/report")
async def get_report(session_id: str):
    db = get_async_db()

    # Fetch all relevant collections
    session      = await db["sessions"].find_one(     {"session_id": session_id}, {"_id": 0})
    grid         = await db["grids"].find_one(         {"session_id": session_id}, {"_id": 0})
    routers      = await db["routers"].find(           {"session_id": session_id}, {"_id": 0}).to_list(200)
    signal       = await db["signal_results"].find_one({"session_id": session_id}, {"_id": 0})
    deadzones    = await db["deadzones"].find_one(     {"session_id": session_id}, {"_id": 0})
    optimisation = await db["optimisation_results"].find_one({"session_id": session_id}, {"_id": 0})
    suggestion   = await db["suggestions"].find_one(  {"session_id": session_id, "accepted": True}, {"_id": 0})

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not signal:
        raise HTTPException(status_code=400, detail="No analysis results found. Run /api/analyse first.")

    data = {
        "session":      session,
        "grid":         grid,
        "routers":      routers,
        "signal":       signal,
        "deadzones":    deadzones,
        "optimisation": optimisation,
        "suggestion":   suggestion,
    }

    pdf_bytes = build_pdf(data)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="DeadZero_{session_id[:8]}.pdf"'
        }
    )
