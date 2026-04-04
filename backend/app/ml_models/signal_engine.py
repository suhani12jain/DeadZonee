"""
signal_engine.py  —  Member 1
DeadZero v3.0 | Signal Engine (NumPy Vectorised)

Wall-aware path loss + device-type-aware interference model.

Device types and their interference behaviour:
  wifi_ap   — 2.4/5/6 GHz, uses CSMA/CA, interferes only with same-band devices
  ble_node  — 2.4 GHz only, no CSMA/CA, always interferes with 2.4 GHz wifi_ap
  iot_node  — 2.4 GHz (Zigbee/Z-Wave), interferes with 2.4 GHz wifi_ap and ble_node
  access_point — same rules as wifi_ap
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
WALL_CROSSING_PENALTY_DB = 3.0

# ── Device type → frequency band mapping ─────────────────────────────────────
# Each device type maps to a set of frequency bands it operates on.
# Two devices interfere only if they share at least one band.
DEVICE_BANDS = {
    "wifi_ap":      {"2.4ghz", "5ghz", "6ghz"},   # depends on frequency_mhz
    "access_point": {"2.4ghz", "5ghz", "6ghz"},   # same as wifi_ap
    "ble_node":     {"2.4ghz"},                    # BLE is always 2.4 GHz
    "iot_node":     {"2.4ghz"},                    # Zigbee/Z-Wave 2.4 GHz band
}

def _freq_to_band(freq_mhz: float) -> str:
    """Map frequency_mhz to band string."""
    if freq_mhz < 3000:
        return "2.4ghz"
    if freq_mhz < 5900:
        return "5ghz"
    return "6ghz"

def _device_bands(device_type: str, freq_mhz: float) -> set:
    """
    Return the set of bands a device actually uses.
    For wifi_ap / access_point, narrow to the specific configured frequency.
    For ble_node / iot_node, always 2.4 GHz regardless of frequency_mhz field.
    """
    dt = (device_type or "wifi_ap").lower()
    if dt in ("wifi_ap", "access_point"):
        return {_freq_to_band(freq_mhz)}
    return DEVICE_BANDS.get(dt, {"2.4ghz"})


# ─────────────────────────────────────────────────────────────────────────────
# Public helper — also imported by M2's optimizer
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# Bresenham line
# ─────────────────────────────────────────────────────────────────────────────
def _bresenham(r0, c0, r1, c1):
    cells = []
    dr = abs(r1 - r0); dc = abs(c1 - c0)
    sr = 1 if r1 > r0 else -1
    sc = 1 if c1 > c0 else -1
    r, c = r0, c0
    if dc > dr:
        err = dc // 2
        while c != c1:
            cells.append((r, c))
            err -= dr
            if err < 0:
                r += sr; err += dc
            c += sc
    else:
        err = dr // 2
        while r != r1:
            cells.append((r, c))
            err -= dc
            if err < 0:
                c += sc; err += dr
            r += sr
    cells.append((r1, c1))
    return cells


# ─────────────────────────────────────────────────────────────────────────────
# Wall-penalty matrix
# ─────────────────────────────────────────────────────────────────────────────
def _build_wall_penalty_matrix(router_row, router_col, zone_grid,
                                grid_rows, grid_cols):
    wall_penalty = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    for r in range(grid_rows):
        for c in range(grid_cols):
            if r == router_row and c == router_col:
                continue
            path      = _bresenham(router_row, router_col, r, c)
            crossings = 0
            prev_zone = zone_grid[path[0][0], path[0][1]]
            for pr, pc in path[1:]:
                curr_zone = zone_grid[pr, pc]
                if curr_zone != prev_zone:
                    crossings += 1
                    prev_zone  = curr_zone
            wall_penalty[r, c] = crossings * WALL_CROSSING_PENALTY_DB
    return wall_penalty


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _channels_interfere_same_band(ch_a: int, ch_b: int, freq_mhz: float) -> bool:
    """
    True if two devices on the SAME frequency band interfere via channel overlap.
    Called only after confirming the two devices share a band.
    """
    if ch_a == ch_b:
        return True
    if freq_mhz < 3000:
        return abs(ch_a - ch_b) < ADJACENT_CHANNELS_24
    return abs(ch_a - ch_b) < ADJACENT_CHANNELS_5


def _devices_interfere(ra: dict, rb: dict) -> bool:
    """
    Master interference check between two router/device dicts.

    Rules:
      1. Devices must share at least one frequency band to interfere at all.
      2. If both are wifi_ap / access_point on the same band, apply channel
         separation rules (non-overlapping channels = no interference).
      3. If either device is ble_node or iot_node AND they share the 2.4 GHz
         band, they ALWAYS interfere regardless of channel — these protocols
         do not respect WiFi channel coordination (no CSMA/CA).
    """
    dt_a = (ra.get("device_type") or "wifi_ap").lower()
    dt_b = (rb.get("device_type") or "wifi_ap").lower()
    freq_a = float(ra.get("frequency_mhz", 2400.0))
    freq_b = float(rb.get("frequency_mhz", 2400.0))

    bands_a = _device_bands(dt_a, freq_a)
    bands_b = _device_bands(dt_b, freq_b)

    shared_bands = bands_a & bands_b
    if not shared_bands:
        return False   # completely different bands — no interference possible

    # If either device is BLE or IoT on the shared 2.4 GHz band,
    # they always interfere (no CSMA/CA coordination)
    non_wifi = {"ble_node", "iot_node"}
    if (dt_a in non_wifi or dt_b in non_wifi) and "2.4ghz" in shared_bands:
        return True

    # Both are wifi_ap / access_point — apply channel separation rules
    ch_a = int(ra.get("channel", 1))
    ch_b = int(rb.get("channel", 1))
    # Use the lower frequency for channel math (both should be same band here)
    ref_freq = min(freq_a, freq_b)
    return _channels_interfere_same_band(ch_a, ch_b, ref_freq)


def _build_attenuation_matrix(cells, grid_rows, grid_cols):
    attn = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    for cell in cells:
        attn[cell["row"], cell["col"]] = float(cell.get("attenuation", 0.0))
    return attn


def _build_zone_grid(cells, grid_rows, grid_cols):
    zone_map  = {}
    zone_grid = np.zeros((grid_rows, grid_cols), dtype=np.int32)
    for cell in cells:
        zt = cell.get("zone_type", "no_zone")
        if zt not in zone_map:
            zone_map[zt] = len(zone_map)
        zone_grid[cell["row"], cell["col"]] = zone_map[zt]
    return zone_grid


def _build_coord_arrays(cells, cell_size_m, grid_rows, grid_cols):
    half   = cell_size_m / 2.0
    cell_x = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    cell_y = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    for cell in cells:
        r = cell["row"]; c = cell["col"]
        cell_x[r, c] = float(cell.get("x_m", c * cell_size_m)) + half
        cell_y[r, c] = float(cell.get("y_m", r * cell_size_m)) + half
    return cell_x, cell_y


def _signal_one_router(router, cell_x, cell_y, attn_matrix,
                        zone_grid, grid_rows, grid_cols):
    cell_size_m = float(router.get("_cell_size_m", 1.0))
    router_col  = int(router.get("col", 0))
    router_row  = int(router.get("row", 0))
    router_x_m  = router_col * cell_size_m + cell_size_m / 2.0
    router_y_m  = router_row * cell_size_m + cell_size_m / 2.0
    tx_power    = float(router.get("tx_power_dbm", 20.0))
    freq_mhz    = float(router.get("frequency_mhz", 2400.0))
    range_m     = float(router.get("range_m", 50.0))

    dx       = cell_x - router_x_m
    dy       = cell_y - router_y_m
    distance = np.sqrt(dx ** 2 + dy ** 2)
    distance = np.maximum(distance, MIN_DISTANCE_M)

    path_loss    = 20.0 * np.log10(distance) + 20.0 * np.log10(freq_mhz) - 27.55
    wall_penalty = _build_wall_penalty_matrix(
        router_row, router_col, zone_grid, grid_rows, grid_cols
    )
    received = tx_power - path_loss - attn_matrix - wall_penalty
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


def _build_interference_matrix(routers, cell_x, cell_y, attn_matrix,
                                zone_grid, grid_rows, grid_cols, cell_size_m):
    rows, cols   = cell_x.shape
    interference = np.zeros((rows, cols), dtype=np.float64)

    n = len(routers)
    for i in range(n):
        for j in range(i + 1, n):
            ra = routers[i]
            rb = routers[j]

            # ── New device-type-aware interference check ──────────────────────
            if not _devices_interfere(ra, rb):
                continue

            ra["_cell_size_m"] = cell_size_m
            rb["_cell_size_m"] = cell_size_m
            sig_a = _signal_one_router(ra, cell_x, cell_y, attn_matrix,
                                        zone_grid, grid_rows, grid_cols)
            sig_b = _signal_one_router(rb, cell_x, cell_y, attn_matrix,
                                        zone_grid, grid_rows, grid_cols)
            both_strong = (sig_a > INTERFERENCE_MARGIN) & (sig_b > INTERFERENCE_MARGIN)
            interference += both_strong.astype(np.float64)

    max_val = interference.max()
    if max_val > 0:
        interference = interference / max_val

    return interference


def _compute_metrics(best_signal, quality_matrix, interference, routers):
    dead_mask    = best_signal <= DEAD_THRESHOLD_DBM
    coverage_pct = float(100.0 * np.mean(~dead_mask))
    valid        = best_signal[best_signal > -200.0]
    avg_signal   = float(np.mean(valid))  if valid.size > 0 else -200.0
    worst_signal = float(np.min(valid))   if valid.size > 0 else -200.0
    interf_score = float(np.mean(interference))

    flat_quality   = [q for row in quality_matrix for q in row]
    high_quality   = sum(1 for q in flat_quality if q in ("EXCELLENT", "GOOD"))
    estimated_cost = sum(float(r.get("cost", 0)) for r in routers)

    return {
        "coverage_pct":       round(coverage_pct, 2),
        "avg_signal":         round(avg_signal, 2),
        "worst_signal":       round(worst_signal, 2),
        "interference_score": round(interf_score, 4),
        "device_count":       high_quality * 5,
        "estimated_cost":     estimated_cost,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────
def compute_signal(session_id: str, db) -> dict:
    sid = session_id

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

    attn_matrix    = _build_attenuation_matrix(cells, grid_rows, grid_cols)
    zone_grid      = _build_zone_grid(cells, grid_rows, grid_cols)
    cell_x, cell_y = _build_coord_arrays(cells, cell_size_m, grid_rows, grid_cols)

    best_signal = np.full((grid_rows, grid_cols), -200.0, dtype=np.float64)
    for router in routers:
        router["_cell_size_m"] = cell_size_m
        best_signal = np.maximum(
            best_signal,
            _signal_one_router(router, cell_x, cell_y, attn_matrix,
                                zone_grid, grid_rows, grid_cols)
        )

    quality_matrix = _build_quality_matrix(best_signal)
    interference   = _build_interference_matrix(
        routers, cell_x, cell_y, attn_matrix,
        zone_grid, grid_rows, grid_cols, cell_size_m
    )
    metrics = _compute_metrics(best_signal, quality_matrix, interference, routers)

    db["signal_results"].replace_one(
        {"session_id": sid},
        {
            "session_id":          sid,
            "signal_matrix":       best_signal.tolist(),
            "quality_matrix":      quality_matrix,
            "interference_matrix": interference.tolist(),
            "metrics":             metrics,
            "computed_at":         datetime.now(timezone.utc),
        },
        upsert=True,
    )

    print(
        f"[signal_engine] {session_id} -> "
        f"coverage={metrics['coverage_pct']}%  "
        f"avg={metrics['avg_signal']} dBm  "
        f"dead={int(np.sum(best_signal <= DEAD_THRESHOLD_DBM))}  "
        f"wall=ON  device_types=ON"
    )

    return {
        "signal_matrix":       best_signal.tolist(),
        "quality_matrix":      quality_matrix,
        "interference_matrix": interference.tolist(),
        "metrics":             metrics,
    }