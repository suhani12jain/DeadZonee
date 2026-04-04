"""
signal_engine.py  —  Member 1
DeadZero v3.0 | Signal Engine (NumPy Vectorised)
"""

import numpy as np
from datetime import datetime, timezone

DEAD_THRESHOLD_DBM   = -85.0
POOR_THRESHOLD_DBM   = -75.0
FAIR_THRESHOLD_DBM   = -67.0
GOOD_THRESHOLD_DBM   = -50.0
INTERFERENCE_MARGIN  = -67.0
ADJACENT_CHANNELS_24 = 5
ADJACENT_CHANNELS_5  = 4
MIN_DISTANCE_M       = 0.1


def weighted_coverage_score(signal_matrix, cells: list,
                             threshold: float = DEAD_THRESHOLD_DBM) -> float:
    total_weight   = 0.0
    covered_weight = 0.0
    for cell in cells:
        r  = cell["row"]
        c  = cell["col"]
        pw = float(cell.get("priority_weight", 0.0))
        total_weight += pw
        if signal_matrix[r][c] > threshold:
            covered_weight += pw
    if total_weight <= 0.0:
        return 0.0
    return (covered_weight / total_weight) * 100.0


def _channels_interfere(ch_a: int, ch_b: int, freq_mhz: float) -> bool:
    if ch_a == ch_b:
        return True
    if freq_mhz < 3000:
        return abs(ch_a - ch_b) < ADJACENT_CHANNELS_24
    return abs(ch_a - ch_b) < ADJACENT_CHANNELS_5


def _build_attenuation_matrix(cells, grid_rows, grid_cols):
    attn = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    for cell in cells:
        attn[cell["row"], cell["col"]] = float(cell.get("attenuation", 0.0))
    return attn


def _build_coord_arrays(cells, cell_size_m, grid_rows, grid_cols):
    half   = cell_size_m / 2.0
    cell_x = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    cell_y = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    for cell in cells:
        r = cell["row"]
        c = cell["col"]
        cell_x[r, c] = float(cell.get("x_m", c * cell_size_m)) + half
        cell_y[r, c] = float(cell.get("y_m", r * cell_size_m)) + half
    return cell_x, cell_y


def _signal_one_router(router, cell_x, cell_y, attn_matrix):
    cell_size_m = float(router.get("_cell_size_m", 1.0))
    router_x_m  = float(router.get("col", 0)) * cell_size_m + cell_size_m / 2.0
    router_y_m  = float(router.get("row", 0)) * cell_size_m + cell_size_m / 2.0
    tx_power    = float(router.get("tx_power_dbm", 20.0))
    freq_mhz    = float(router.get("frequency_mhz", 2400.0))
    # ── Respect range_m: cells beyond range get floored to -200 dBm ──────────
    range_m     = float(router.get("range_m", 50.0))

    dx       = cell_x - router_x_m
    dy       = cell_y - router_y_m
    distance = np.sqrt(dx ** 2 + dy ** 2)
    distance = np.maximum(distance, MIN_DISTANCE_M)

    path_loss = 20.0 * np.log10(distance) + 20.0 * np.log10(freq_mhz) - 27.55
    received  = tx_power - path_loss - attn_matrix

    # Zero out signal beyond the router's stated range
    received[distance > range_m] = -200.0

    return received


def _build_quality_matrix(best_signal):
    conditions = [
        best_signal > GOOD_THRESHOLD_DBM,
        best_signal > FAIR_THRESHOLD_DBM,
        best_signal > POOR_THRESHOLD_DBM,
        best_signal > DEAD_THRESHOLD_DBM,
    ]
    choices = ["EXCELLENT", "GOOD", "FAIR", "POOR"]
    return np.select(conditions, choices, default="DEAD").tolist()


def _build_interference_matrix(routers, cell_x, cell_y, attn_matrix, cell_size_m):
    rows, cols   = cell_x.shape
    interference = np.zeros((rows, cols), dtype=np.float64)

    n = len(routers)
    for i in range(n):
        for j in range(i + 1, n):
            ra = routers[i]
            rb = routers[j]
            if not _channels_interfere(
                int(ra.get("channel", 1)),
                int(rb.get("channel", 1)),
                float(ra.get("frequency_mhz", 2400.0))
            ):
                continue
            ra["_cell_size_m"] = cell_size_m
            rb["_cell_size_m"] = cell_size_m
            sig_a = _signal_one_router(ra, cell_x, cell_y, attn_matrix)
            sig_b = _signal_one_router(rb, cell_x, cell_y, attn_matrix)
            # Only cells where BOTH routers exceed the interference margin
            # AND both are within their respective range_m (already handled
            # by _signal_one_router returning -200 beyond range)
            both_strong = (sig_a > INTERFERENCE_MARGIN) & (sig_b > INTERFERENCE_MARGIN)
            interference += both_strong.astype(np.float64)

    # Normalise to 0–1 so frontend threshold of 0.5 is meaningful
    max_val = interference.max()
    if max_val > 0:
        interference = interference / max_val

    return interference


def _compute_metrics(best_signal, quality_matrix, interference, routers):
    dead_mask    = best_signal <= DEAD_THRESHOLD_DBM
    coverage_pct = float(100.0 * np.mean(~dead_mask))
    avg_signal   = float(np.mean(best_signal[best_signal > -200.0])) if np.any(best_signal > -200.0) else -200.0
    worst_signal = float(np.min(best_signal[best_signal > -200.0])) if np.any(best_signal > -200.0) else -200.0
    interf_score = float(np.mean(interference))

    flat_quality = [q for row in quality_matrix for q in row]
    high_quality = sum(1 for q in flat_quality if q in ("EXCELLENT", "GOOD"))
    device_count = high_quality * 5
    estimated_cost = sum(float(r.get("cost", 0)) for r in routers)

    return {
        "coverage_pct":       round(coverage_pct, 2),
        "avg_signal":         round(avg_signal, 2),
        "worst_signal":       round(worst_signal, 2),
        "interference_score": round(interf_score, 4),
        "device_count":       device_count,
        "estimated_cost":     estimated_cost,
    }


def compute_signal_matrices(
    cells: list,
    grid_rows: int,
    grid_cols: int,
    cell_size_m: float,
    routers: list,
) -> dict:
    """
    Pure in-memory signal propagation (same path-loss math as Mongo-backed flow).
    Does not read or write the database.
    """
    if not routers:
        raise ValueError("Place at least one router before running signal simulation.")

    attn_matrix    = _build_attenuation_matrix(cells, grid_rows, grid_cols)
    cell_x, cell_y = _build_coord_arrays(cells, cell_size_m, grid_rows, grid_cols)

    best_signal = np.full((grid_rows, grid_cols), -200.0, dtype=np.float64)
    for router in routers:
        r = dict(router)
        r["_cell_size_m"] = cell_size_m
        best_signal = np.maximum(best_signal, _signal_one_router(r, cell_x, cell_y, attn_matrix))

    quality_matrix = _build_quality_matrix(best_signal)
    interference   = _build_interference_matrix(routers, cell_x, cell_y, attn_matrix, cell_size_m)
    metrics        = _compute_metrics(best_signal, quality_matrix, interference, routers)

    return {
        "signal_matrix":       best_signal.tolist(),
        "quality_matrix":      quality_matrix,
        "interference_matrix": interference.tolist(),
        "metrics":             metrics,
    }


def compute_signal(session_id: str, db) -> dict:
    sid = session_id  # plain UUID string — never ObjectId

    session = db["sessions"].find_one({"session_id": sid})
    if session is None:
        raise ValueError(f"Session '{session_id}' not found in MongoDB.")

    grid_rows   = int(session["grid_rows"])
    grid_cols   = int(session["grid_cols"])
    cell_size_m = float(session["cell_size_m"])

    grid_doc = db["grids"].find_one({"session_id": sid})
    if grid_doc is None:
        raise ValueError(f"No grid found for session '{session_id}'.")
    cells = grid_doc["cells"]

    routers = list(db["routers"].find({"session_id": sid}))
    if not routers:
        raise ValueError(
            f"No routers placed for session '{session_id}'. "
            "Place at least one router before running analysis."
        )

    result = compute_signal_matrices(cells, grid_rows, grid_cols, cell_size_m, routers)
    best_signal = np.array(result["signal_matrix"], dtype=np.float64)

    db["signal_results"].replace_one(
        {"session_id": sid},
        {
            "session_id":          sid,
            "signal_matrix":       result["signal_matrix"],
            "quality_matrix":      result["quality_matrix"],
            "interference_matrix": result["interference_matrix"],
            "metrics":             result["metrics"],
            "computed_at":         datetime.now(timezone.utc),
        },
        upsert=True,
    )

    print(
        f"[signal_engine] Session {session_id} -> "
        f"coverage={result['metrics']['coverage_pct']}%  "
        f"avg={result['metrics']['avg_signal']} dBm  "
        f"dead_cells={int(np.sum(best_signal <= DEAD_THRESHOLD_DBM))}"
    )

    return {
        "signal_matrix":       result["signal_matrix"],
        "quality_matrix":      result["quality_matrix"],
        "interference_matrix": result["interference_matrix"],
        "metrics":             result["metrics"],
    }