"""
database/schemas.py
-------------------
Pydantic models for all FastAPI request bodies.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ── Device type enum ──────────────────────────────────────────────────────────
class DeviceType(str, Enum):
    wifi_ap       = "wifi_ap"        # Standard WiFi access point — CSMA/CA, channel-aware
    access_point  = "access_point"   # Alias for wifi_ap
    ble_node      = "ble_node"       # Bluetooth Low Energy — always interferes on 2.4 GHz
    iot_node      = "iot_node"       # Zigbee / Z-Wave IoT — always interferes on 2.4 GHz


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
    session_id:  str
    width_m:     Optional[float] = None
    height_m:    Optional[float] = None
    cell_size_m: Optional[float] = None


class CellPayload(BaseModel):
    row:             int
    col:             int
    zone_type:       str   = "no_zone"
    attenuation:     float = 99.0
    priority_weight: float = 0.0
    allow_router:    bool  = False


class SaveZonesPayload(BaseModel):
    session_id: str
    cells:      List[CellPayload]


# ── Routers ───────────────────────────────────────────────────────────────────
class RouterCreate(BaseModel):
    session_id:    str
    name:          str
    row:           int
    col:           int
    tx_power_dbm:  float      = 20.0
    frequency_mhz: float      = 2400.0
    channel:       int        = 1
    range_m:       float      = 50.0
    cost:          float      = 2000.0
    is_suggested:  bool       = False
    device_type:   DeviceType = DeviceType.wifi_ap   # ← NEW


class RouterUpdate(BaseModel):
    name:          Optional[str]        = None
    row:           Optional[int]        = None
    col:           Optional[int]        = None
    tx_power_dbm:  Optional[float]      = None
    frequency_mhz: Optional[float]      = None
    channel:       Optional[int]        = None
    range_m:       Optional[float]      = None
    cost:          Optional[float]      = None
    device_type:   Optional[DeviceType] = None       # ← NEW


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