"""
What-If Agent — in-memory floor-plan experiments (no Mongo writes).

Loads grid + routers from DB, deep-copies cells, applies hypothetical zone patches,
runs signal_engine twice, compares, optionally uses Claude for NL parse + summary.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, List, Optional, Tuple

import anthropic
import numpy as np
from dotenv import load_dotenv

from app.ml_models.signal_engine import (
    DEAD_THRESHOLD_DBM,
    compute_signal_matrices,
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env"))

ANTHROPIC_KEY = os.getenv("ANTHROPIC_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Mirrors frontend zoneConfig.js (+ concrete_wall for demos)
ZONE_DEFAULTS: dict[str, tuple[float, float, bool]] = {
    "office": (6.0, 1.5, True),
    "meeting_room": (5.0, 1.2, True),
    "bathroom": (7.0, 0.3, False),
    "corridor": (2.0, 0.8, True),
    "lobby": (3.0, 1.0, True),
    "server_room": (9.0, 2.2, False),
    "staircase": (4.0, 0.4, False),
    "storage": (5.0, 0.3, False),
    "outdoor": (1.0, 0.5, True),
    "no_zone": (99.0, 0.0, False),
    "concrete_wall": (18.0, 0.2, False),
    "drywall": (4.0, 0.5, False),
    "glass_wall": (2.5, 0.6, True),
}


def _zone_props(zone_type: str) -> tuple[float, float, bool]:
    z = (zone_type or "no_zone").strip().lower().replace(" ", "_").replace("-", "_")
    if z not in ZONE_DEFAULTS:
        # Unknown NL zone → heavy obstruction
        return (15.0, 0.1, False)
    return ZONE_DEFAULTS[z]


def _apply_zone_to_cell(cell: dict, zone_type: str) -> dict:
    raw = (zone_type or "no_zone").strip()
    z = raw.lower().replace(" ", "_").replace("-", "_")
    if z in ZONE_DEFAULTS:
        att, pw, ar = ZONE_DEFAULTS[z]
        canonical = z
    else:
        att, pw, ar = _zone_props(z)
        canonical = raw
    out = dict(cell)
    out["zone_type"] = canonical
    out["attenuation"] = att
    out["priority_weight"] = pw
    out["allow_router"] = ar
    return out


def apply_rect_change(
    cells: List[dict],
    grid_rows: int,
    grid_cols: int,
    row_min: int,
    row_max: int,
    col_min: int,
    col_max: int,
    zone_type: str,
) -> List[dict]:
    """Return a new cell list with rectangle [row_min,row_max] x [col_min,col_max] updated."""
    rm0, rx0 = min(row_min, row_max), max(row_min, row_max)
    cm0, cx0 = min(col_min, col_max), max(col_min, col_max)
    rm = max(0, min(rm0, grid_rows - 1))
    rx = max(0, min(rx0, grid_rows - 1))
    cm = max(0, min(cm0, grid_cols - 1))
    cx = max(0, min(cx0, grid_cols - 1))

    index = {(int(c["row"]), int(c["col"])): i for i, c in enumerate(cells)}
    new_cells = list(cells)
    for r in range(rm, rx + 1):
        for c in range(cm, cx + 1):
            i = index.get((r, c))
            if i is None:
                continue
            new_cells[i] = _apply_zone_to_cell(dict(new_cells[i]), zone_type)
    return new_cells


def _parse_claude_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Claude did not return JSON")
    return json.loads(m.group(0))


def _guess_zone_from_words(q: str) -> str:
    ql = q.lower()
    if "concrete" in ql or re.search(r"\bwall\b", ql):
        return "concrete_wall"
    if "server" in ql and "room" in ql:
        return "server_room"
    for name in sorted(ZONE_DEFAULTS.keys(), key=len, reverse=True):
        if name.replace("_", " ") in ql or name in ql:
            return name
    return "concrete_wall"


def _parse_query_fallback(query: str, grid_rows: int, grid_cols: int) -> List[dict]:
    """
    No-API fallback for short, structured English (demo / offline).
    Understands full row, full column, and row/col ranges. 0-based indices.
    """
    q = query.strip()
    if not q:
        return []
    ql = q.lower()
    zone = _guess_zone_from_words(ql)

    # row A to B, cols C to D
    m = re.search(
        r"row\s+(\d+)\s*(?:to|-|through)\s*(\d+).*"
        r"col(?:umn)?s?\s+(\d+)\s*(?:to|-|through)\s*(\d+)",
        ql,
    )
    if m:
        r0, r1, c0, c1 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        ra, rb = min(r0, r1), max(r0, r1)
        ca, cb = min(c0, c1), max(c0, c1)
        return [{
            "row_min": max(0, min(ra, grid_rows - 1)),
            "row_max": max(0, min(rb, grid_rows - 1)),
            "col_min": max(0, min(ca, grid_cols - 1)),
            "col_max": max(0, min(cb, grid_cols - 1)),
            "zone": zone,
        }]

    # row R, columns C to D (single row band)
    m = re.search(
        r"row\s+(\d+).*col(?:umn)?s?\s+(\d+)\s*(?:to|-|through)\s*(\d+)",
        ql,
    )
    if m:
        r, c0, c1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= r < grid_rows:
            return [{
                "row_min": r,
                "row_max": r,
                "col_min": max(0, min(c0, c1, grid_cols - 1)),
                "col_max": max(0, min(max(c0, c1), grid_cols - 1)),
                "zone": zone,
            }]

    # rows R0 to R1 (full width)
    m = re.search(r"row\s+(\d+)\s*(?:to|-|through)\s*(\d+)", ql)
    if m and "col" not in ql.split("row", 1)[-1][:50]:
        r0, r1 = int(m.group(1)), int(m.group(2))
        ra, rb = min(r0, r1), max(r0, r1)
        return [{
            "row_min": max(0, min(ra, grid_rows - 1)),
            "row_max": max(0, min(rb, grid_rows - 1)),
            "col_min": 0,
            "col_max": grid_cols - 1,
            "zone": zone,
        }]

    # single full row: "row 3", "across row 3"
    m = re.search(r"\brow\s+(\d+)\b", ql)
    if m:
        r = int(m.group(1))
        if 0 <= r < grid_rows:
            return [{
                "row_min": r,
                "row_max": r,
                "col_min": 0,
                "col_max": grid_cols - 1,
                "zone": zone,
            }]

    # full column "column 4"
    m = re.search(r"\bcol(?:umn)?\s+(\d+)\b", ql)
    if m:
        c = int(m.group(1))
        if 0 <= c < grid_cols:
            return [{
                "row_min": 0,
                "row_max": grid_rows - 1,
                "col_min": c,
                "col_max": c,
                "zone": zone,
            }]

    return []


def parse_natural_language_change(
    query: str,
    grid_rows: int,
    grid_cols: int,
    api_key: Optional[str],
) -> List[dict]:
    """
    Ask Claude to emit JSON:
    { "changes": [ { "row_min", "row_max", "col_min", "col_max", "zone": "concrete_wall" }, ... ] }
    Indices are 0-based, inclusive, matching the UI hover [row,col].
    """
    key = api_key or ANTHROPIC_KEY
    if not key or key.startswith("your_"):
        fb = _parse_query_fallback(query, grid_rows, grid_cols)
        if fb:
            return fb
        raise ValueError(
            "No ANTHROPIC_KEY: use 'Add hovered cell' with an empty English box, or set "
            "ANTHROPIC_KEY in backend/.env for free-form English. You can also try a short "
            "phrase the offline parser understands, e.g. 'concrete wall row 3' or "
            "'row 2 col 0 to 8'."
        )

    valid = ", ".join(sorted(ZONE_DEFAULTS.keys()))
    prompt = f"""You convert WiFi floor-plan edit requests into JSON only.

Grid size: {grid_rows} rows × {grid_cols} columns (0-based indices).
Valid zone keys: {valid}

User request: {query!r}

Return a single JSON object with this exact shape (no markdown):
{{"changes":[{{"row_min":0,"row_max":0,"col_min":0,"col_max":9,"zone":"concrete_wall"}}]}}

Rules:
- Use inclusive row_min/row_max and col_min/col_max.
- "row 3" means row index 3.
- If the user describes a full row, set col_min=0 and col_max={grid_cols - 1}.
- If unclear, pick the smallest interpretation that matches the words.
- Use zone keys from the valid list; map "concrete" or "wall" to concrete_wall when appropriate.
"""

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    data = _parse_claude_json(raw)
    changes = data.get("changes") or []
    if not isinstance(changes, list):
        raise ValueError("Invalid Claude response: changes must be a list")
    normalized = []
    for ch in changes:
        if not isinstance(ch, dict):
            continue
        normalized.append({
            "row_min": int(ch["row_min"]),
            "row_max": int(ch["row_max"]),
            "col_min": int(ch["col_min"]),
            "col_max": int(ch["col_max"]),
            "zone": str(ch.get("zone", "concrete_wall")),
        })
    return normalized


def explain_what_if(summary: dict, api_key: Optional[str] = None) -> str:
    """Three-sentence physical explanation from aggregate stats."""
    key = api_key or ANTHROPIC_KEY
    blob = json.dumps(summary, indent=2)
    fallback = (
        f"Coverage moved from {summary.get('coverage_before_pct')}% to "
        f"{summary.get('coverage_after_pct')}%. "
        f"Higher attenuation in the edited cells weakens received power along those paths. "
        f"Dead-zone cells changed by {summary.get('net_dead_change', 0):+d} net."
    )
    if not key or key.startswith("your_"):
        return fallback
    try:
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=220,
            messages=[{
                "role": "user",
                "content": (
                    "You are an RF engineer. In exactly 3 short sentences, explain this WiFi "
                    "what-if simulation to a facilities manager. Mention walls/attenuation/path "
                    "loss in plain language. Data:\n" + blob
                ),
            }],
        )
        return response.content[0].text.strip()
    except Exception:
        return fallback


def compare_signals(
    before: List[List[float]],
    after: List[List[float]],
) -> Tuple[np.ndarray, dict]:
    """Delta = after - before (dB). Count dead-cell transitions."""
    b = np.array(before, dtype=np.float64)
    a = np.array(after, dtype=np.float64)
    delta = a - b

    dead_b = b <= DEAD_THRESHOLD_DBM
    dead_a = a <= DEAD_THRESHOLD_DBM
    new_dead = dead_a & ~dead_b
    recovered = dead_b & ~dead_a

    return delta, {
        "new_dead_count": int(np.sum(new_dead)),
        "recovered_count": int(np.sum(recovered)),
        "new_dead_mask": new_dead.astype(np.int32).tolist(),
        "recovered_mask": recovered.astype(np.int32).tolist(),
    }


def run_what_if(
    session: dict,
    grid_doc: dict,
    routers: List[dict],
    query: Optional[str],
    manual_changes: Optional[List[dict]],
    anthropic_key: Optional[str] = None,
) -> dict:
    """
    manual_changes: list of {row_min, row_max, col_min, col_max, zone} or
    {row, col, zone} for a single cell.
    """
    grid_rows = int(session["grid_rows"])
    grid_cols = int(session["grid_cols"])
    cell_size_m = float(session.get("cell_size_m", grid_doc.get("cell_size_m", 2.0)))
    cells_orig = copy.deepcopy(grid_doc["cells"])
    if len(cells_orig) != grid_rows * grid_cols:
        # still allow if list matches topology
        pass

    api_key = anthropic_key or ANTHROPIC_KEY
    structured: List[dict] = []

    if query and query.strip():
        structured.extend(parse_natural_language_change(query.strip(), grid_rows, grid_cols, api_key))

    if manual_changes:
        for ch in manual_changes:
            if "row" in ch and "col" in ch:
                r, c = int(ch["row"]), int(ch["col"])
                structured.append({
                    "row_min": r, "row_max": r, "col_min": c, "col_max": c,
                    "zone": str(ch.get("zone_type") or ch.get("zone", "concrete_wall")),
                })
            else:
                structured.append({
                    "row_min": int(ch["row_min"]),
                    "row_max": int(ch["row_max"]),
                    "col_min": int(ch["col_min"]),
                    "col_max": int(ch["col_max"]),
                    "zone": str(ch.get("zone_type") or ch.get("zone", "concrete_wall")),
                })

    if not structured:
        raise ValueError("Provide a natural-language query and/or manual_changes.")

    cells_after = copy.deepcopy(cells_orig)
    for rect in structured:
        cells_after = apply_rect_change(
            cells_after,
            grid_rows,
            grid_cols,
            rect["row_min"],
            rect["row_max"],
            rect["col_min"],
            rect["col_max"],
            rect["zone"],
        )

    before = compute_signal_matrices(cells_orig, grid_rows, grid_cols, cell_size_m, routers)
    after = compute_signal_matrices(cells_after, grid_rows, grid_cols, cell_size_m, routers)

    sig_b = before["signal_matrix"]
    sig_a = after["signal_matrix"]
    delta_np, flip = compare_signals(sig_b, sig_a)

    cov_b = float(before["metrics"]["coverage_pct"])
    cov_a = float(after["metrics"]["coverage_pct"])

    summary = {
        "coverage_before_pct": cov_b,
        "coverage_after_pct": cov_a,
        "avg_signal_before_dbm": before["metrics"].get("avg_signal"),
        "avg_signal_after_dbm": after["metrics"].get("avg_signal"),
        "new_dead_cells": flip["new_dead_count"],
        "recovered_dead_cells": flip["recovered_count"],
        "net_dead_change": flip["new_dead_count"] - flip["recovered_count"],
        "applied_changes": structured,
    }
    explanation = explain_what_if(summary, api_key)

    return {
        "applied_changes": structured,
        "metrics_before": before["metrics"],
        "metrics_after": after["metrics"],
        "signal_before": sig_b,
        "signal_after": sig_a,
        "delta_matrix": delta_np.tolist(),
        "new_dead_mask": flip["new_dead_mask"],
        "recovered_mask": flip["recovered_mask"],
        "explanation": explanation,
        "summary": summary,
    }
