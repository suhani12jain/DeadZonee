"""
database/schemas.py
-------------------
Pydantic models for all FastAPI request bodies.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ── Session ───────────────────────────────────────────────────────────────────
class SessionCreate(BaseModel):
    project_name:  str
    building_name: str   = ""
    width_m:       float = Field(gt=0)
    height_m:      float = Field(gt=0)
    cell_size_m:   float = Field(gt=0)


# ── Grid ──────────────────────────────────────────────────────────────────────
class SessionIDPayload(BaseModel):
    session_id: str


class GridCreatePayload(BaseModel):
    """
    Used by POST /api/grid/create.
    Frontend sends session_id + dimensions together.
    Backend can use stored session dims OR use these directly.
    """
    session_id:  str
    width_m:     Optional[float] = None   # optional — fallback to session values
    height_m:    Optional[float] = None
    cell_size_m: Optional[float] = None


class CellPayload(BaseModel):
    row:            int
    col:            int
    zone_type:      str   = "no_zone"
    attenuation:    float = 99.0
    priority_weight:float = 0.0
    allow_router:   bool  = False


class SaveZonesPayload(BaseModel):
    session_id: str
    cells:      List[CellPayload]


# ── Routers ───────────────────────────────────────────────────────────────────
class RouterCreate(BaseModel):
    session_id:    str
    name:          str
    row:           int
    col:           int
    tx_power_dbm:  float = 20.0
    frequency_mhz: float = 2400.0
    channel:       int   = 1
    range_m:       float = 50.0
    cost:          float = 2000.0
    is_suggested:  bool  = False


class RouterUpdate(BaseModel):
    name:          Optional[str]   = None
    row:           Optional[int]   = None
    col:           Optional[int]   = None
    tx_power_dbm:  Optional[float] = None
    frequency_mhz: Optional[float] = None
    channel:       Optional[int]   = None
    range_m:       Optional[float] = None
    cost:          Optional[float] = None


class AcceptSuggestionPayload(BaseModel):
    session_id:    str
    suggestion_id: str


# ── Analysis ──────────────────────────────────────────────────────────────────
class AnalysePayload(BaseModel):
    session_id: str


# ── Optimise ──────────────────────────────────────────────────────────────────
class OptimisePayload(BaseModel):
    session_id: str


# ── Suggest ───────────────────────────────────────────────────────────────────
class SuggestPayload(BaseModel):
    session_id: str