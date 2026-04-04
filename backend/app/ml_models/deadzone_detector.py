"""
deadzone_detector.py  —  Member 1
DeadZero v3.0 | NumPy + SciPy Dead Zone Detector

Reads signal_matrix from MongoDB 'signal_results' collection.
Uses vectorised NumPy for threshold masking and SciPy ndimage
for connected-component clustering. No BFS/DFS — pure C-speed ops.

Function signature (called by M3's FastAPI route):
    detect_deadzones(session_id: str, db) -> dict
"""

import numpy as np
from scipy import ndimage
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
DEAD_THRESHOLD_DBM = -85.0
MIN_CLUSTER_SIZE   = 3
STRUCT_4CONNECT    = ndimage.generate_binary_structure(2, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _build_clusters(dead_mask: np.ndarray,
                    labeled:   np.ndarray,
                    num_clusters: int) -> list:
    clusters = []
    for cluster_id in range(1, num_clusters + 1):
        cluster_mask = labeled == cluster_id
        size = int(np.sum(cluster_mask))

        if size <= MIN_CLUSTER_SIZE:
            continue

        centroid     = ndimage.center_of_mass(dead_mask, labeled, cluster_id)
        cell_rows, cell_cols = np.where(cluster_mask)
        cells = [
            {"row": int(r), "col": int(c)}
            for r, c in zip(cell_rows.tolist(), cell_cols.tolist())
        ]

        clusters.append({
            "cluster_id":   cluster_id,
            "size":         size,
            "centroid_row": round(float(centroid[0]), 2),
            "centroid_col": round(float(centroid[1]), 2),
            "cells":        cells,
        })

    clusters.sort(key=lambda x: x["size"], reverse=True)
    for idx, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = idx

    return clusters


# ─────────────────────────────────────────────────────────────────────────────
# Main public function — called by M3's FastAPI route
# ─────────────────────────────────────────────────────────────────────────────
def detect_deadzones(session_id: str, db) -> dict:
    """
    Entry point called by Member 3's FastAPI route:
        POST /api/deadzones -> deadzones.py -> detect_deadzones(session_id, db)

    session_id is a plain UUID string — never converted to ObjectId.
    All MongoDB queries use {"session_id": session_id}.
    """
    # session_id is a plain UUID string — NEVER convert to ObjectId
    sid = session_id

    # ── 1. Fetch signal_matrix from MongoDB ───────────────────────────────────
    signal_doc = db["signal_results"].find_one({"session_id": sid})
    if signal_doc is None:
        raise ValueError(
            f"No signal results found for session '{session_id}'. "
            "Run /api/analyse (signal step) first."
        )

    signal_matrix = np.array(signal_doc["signal_matrix"], dtype=np.float64)
    rows, cols    = signal_matrix.shape

    # ── 2. Dead zone mask — ONE line ──────────────────────────────────────────
    dead_mask = signal_matrix < DEAD_THRESHOLD_DBM

    # ── 3. Label connected clusters — TWO lines ───────────────────────────────
    labeled, num_clusters = ndimage.label(dead_mask, structure=STRUCT_4CONNECT)

    # ── 4. Build cluster stats ────────────────────────────────────────────────
    clusters   = _build_clusters(dead_mask, labeled, num_clusters)
    dead_count = int(np.sum(dead_mask))

    print(
        f"[deadzone_detector] Session {session_id} -> "
        f"dead_cells={dead_count}/{rows*cols}  "
        f"raw_clusters={num_clusters}  "
        f"filtered_clusters={len(clusters)}"
    )

    # ── 5. Upsert to MongoDB ──────────────────────────────────────────────────
    db["deadzones"].replace_one(
        {"session_id": sid},
        {
            "session_id":      sid,
            "dead_zone_mask":  dead_mask.tolist(),
            "dead_zone_count": dead_count,
            "clusters":        clusters,
            "computed_at":     datetime.now(timezone.utc),
        },
        upsert=True,
    )

    # Return JSON-safe version
    return {
        "dead_zone_mask":  dead_mask.tolist(),
        "dead_zone_count": dead_count,
        "clusters":        clusters,
    }