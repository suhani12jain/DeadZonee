# backend/app/ml_models/placement_suggester.py
import os
import uuid
import numpy as np
import anthropic
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../../.env'))

MONGO_URL     = os.getenv("MONGO_URL")
DB_NAME       = os.getenv("DB_NAME", "deadzone01")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_KEY", "")


# ---------------------------------------------------------------------------
# SPIRAL SEARCH — find nearest allow_router=True cell from a centroid
# ---------------------------------------------------------------------------
def _spiral_find_valid_cell(centroid_row, centroid_col,
                             cell_map, grid_rows, grid_cols, max_radius=20):
    # Searches outward radius 0, 1, 2, ... until a valid cell is found.
    # Returns (row, col) of nearest allow_router=True cell.
    cr, cc = int(round(centroid_row)), int(round(centroid_col))
    for radius in range(0, max_radius + 1):
        if radius == 0:
            candidates = [(cr, cc)]
        else:
            candidates = []
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if abs(dr) == radius or abs(dc) == radius:
                        r, c = cr + dr, cc + dc
                        if 0 <= r < grid_rows and 0 <= c < grid_cols:
                            candidates.append((r, c))
        for r, c in candidates:
            cell = cell_map.get((r, c), {})
            if cell.get('allow_router', False):
                return r, c
    return (max(0, min(cr, grid_rows-1)), max(0, min(cc, grid_cols-1)))


# ---------------------------------------------------------------------------
# CHANNEL SELECTION
# For 2.4 GHz prefer non-overlapping: 1, 6, 11
# For 5 GHz prefer: 36, 40, 44, 48, 149, 153, 157, 161
# ---------------------------------------------------------------------------
def _pick_channel(existing_routers, frequency_mhz, suggested_row,
                  suggested_col, cell_size_m, range_m=50):
    if frequency_mhz < 3000:
        preferred = [1, 6, 11]
    else:
        preferred = [36, 40, 44, 48, 149, 153, 157, 161]

    channel_counts = {ch: 0 for ch in preferred}
    for r in existing_routers:
        dr = abs(r['row'] - suggested_row) * cell_size_m
        dc = abs(r['col'] - suggested_col) * cell_size_m
        dist = (dr**2 + dc**2) ** 0.5
        if dist <= range_m:
            ch = r.get('channel', 1)
            if ch in channel_counts:
                channel_counts[ch] += 1
    return min(channel_counts, key=channel_counts.get)


# ---------------------------------------------------------------------------
# ESTIMATE COVERAGE GAIN
# Count dead cells within range_cells radius of the suggested position.
# ---------------------------------------------------------------------------
def _estimate_coverage_gain(signal_matrix, dead_mask, suggested_row,
                             suggested_col, range_cells, grid_rows, grid_cols):
    total_cells = grid_rows * grid_cols
    gained = 0
    for dr in range(-range_cells, range_cells + 1):
        for dc in range(-range_cells, range_cells + 1):
            r = suggested_row + dr
            c = suggested_col + dc
            if 0 <= r < grid_rows and 0 <= c < grid_cols:
                if dead_mask[r][c]:
                    gained += 1
    return (gained / total_cells) * 100.0 if total_cells > 0 else 0.0


# ---------------------------------------------------------------------------
# CLAUDE API — 3-sentence placement strategy
# Falls back to template if API key missing or call fails.
# ---------------------------------------------------------------------------
def _call_claude(cluster_size, row, col, zone_type, priority_weight,
                 channel, frequency_mhz, api_key):
    fallback = (
        f"A dead zone of {cluster_size} cells was detected at row {row}, "
        f"column {col} in the {zone_type.replace('_', ' ')} area "
        f"(priority weight: {priority_weight:.1f}). "
        f"Placing a router here on channel {channel} ({frequency_mhz} MHz) "
        f"will restore coverage to this high-demand zone. "
        f"Ensure the router has clear line-of-sight and is mounted at "
        f"ceiling height for best results."
    )
    if not api_key or api_key.startswith("your_"):
        print("[placement_suggester] No Anthropic API key — using fallback")
        return fallback
    try:
        prompt = (
            f"Campus dead zone detected. Cluster size: {cluster_size} cells. "
            f"Location: row {row}, col {col}. Zone type: {zone_type}. "
            f"Priority weight: {priority_weight:.1f}. "
            f"Proposed router: channel {channel}, {frequency_mhz} MHz. "
            f"Suggest router placement strategy in exactly 3 sentences."
        )
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=200,
            timeout=10,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"[placement_suggester] Claude API failed ({e}) — using fallback")
        return fallback


# ---------------------------------------------------------------------------
# MAIN ENTRYPOINT — called by M3's FastAPI route
# ---------------------------------------------------------------------------
def suggest_placement(session_id: str, db, anthropic_key: str = None) -> dict:
    api_key = anthropic_key or ANTHROPIC_KEY

    # 1. Read session
    session = db.sessions.find_one({'session_id': session_id})
    if not session:
        raise ValueError(f"Session {session_id} not found")
    grid_rows   = session['grid_rows']
    grid_cols   = session['grid_cols']
    cell_size_m = session.get('cell_size_m', 2.0)

    # 2. Read dead zone clusters
    dz_doc = db.deadzones.find_one({'session_id': session_id})
    if not dz_doc:
        raise ValueError("No dead zone data found. Run analysis first.")
    clusters = dz_doc.get('clusters', [])
    if not clusters:
        raise ValueError("No dead zone clusters found — coverage may already be complete.")

    # 3. Read grid cells
    grid_doc = db.grids.find_one({'session_id': session_id})
    if not grid_doc:
        raise ValueError("Grid not found for session")
    cells_flat = grid_doc['cells']
    cell_map   = {(c['row'], c['col']): c for c in cells_flat}

    # 4. Read existing routers
    existing_routers = list(db.routers.find({'session_id': session_id}))

    # 5. Read signal matrix for coverage gain estimation
    sig_doc    = db.signal_results.find_one({'session_id': session_id})
    signal_mat = sig_doc.get('signal_matrix', []) if sig_doc else []
    dead_mask_arr = np.array(dz_doc.get('dead_zone_mask', []), dtype=bool)

    # 6. Rank dead zone clusters by priority = size x priority_weight_at_centroid
    for cluster in clusters:
        cr   = cluster.get('centroid_row', 0)
        cc   = cluster.get('centroid_col', 0)
        cell = cell_map.get((int(round(cr)), int(round(cc))), {})
        pw   = float(cell.get('priority_weight', 0.1))
        cluster['_priority'] = cluster.get('size', 1) * pw

    best_cluster = max(clusters, key=lambda x: x.get('_priority', 0))
    centroid_r   = best_cluster.get('centroid_row', 0)
    centroid_c   = best_cluster.get('centroid_col', 0)
    cluster_sz   = best_cluster.get('size', 1)

    # 7. Find nearest valid placement cell (allow_router=True)
    sug_row, sug_col = _spiral_find_valid_cell(
        centroid_r, centroid_c, cell_map, grid_rows, grid_cols)

    best_cell  = cell_map.get((sug_row, sug_col), {})
    zone_type  = best_cell.get('zone_type', 'corridor')
    pw_at_cell = float(best_cell.get('priority_weight', 0.5))

    # 8. Config
    frequency_mhz = 2400
    range_m       = 50.0
    tx_power      = 20.0
    channel       = _pick_channel(existing_routers, frequency_mhz,
                                  sug_row, sug_col, cell_size_m, range_m)

    # 9. Estimate coverage gain
    range_cells   = int(range_m / cell_size_m)
    coverage_gain = 0.0
    if dead_mask_arr.size > 0:
        coverage_gain = _estimate_coverage_gain(
            signal_mat, dead_mask_arr,
            sug_row, sug_col, range_cells, grid_rows, grid_cols)

    # 10. Call Claude API
    explanation = _call_claude(cluster_sz, sug_row, sug_col, zone_type,
                                pw_at_cell, channel, frequency_mhz, api_key)

    # 11. Write to MongoDB
    suggestion_id  = str(uuid.uuid4())
    suggestion_doc = {
        '_id':               suggestion_id,
        'session_id':        session_id,
        'suggested_row':     sug_row,
        'suggested_col':     sug_col,
        'suggested_config':  {
            'tx_power':  tx_power,
            'frequency': frequency_mhz,
            'channel':   channel,
            'range':     range_m,
        },
        'explanation':       explanation,
        'coverage_gain_pct': float(coverage_gain),
        'accepted':          False,
    }
    db.suggestions.insert_one(suggestion_doc)
    return {**suggestion_doc, 'suggestion_id': suggestion_id}


# ---------------------------------------------------------------------------
# STANDALONE TEST — python3 backend/app/ml_models/placement_suggester.py <sid>
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python placement_suggester.py <session_id>")
        sys.exit(1)
    session_id = sys.argv[1]
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        result = suggest_placement(session_id, db)
        print(f"Suggested : row={result['suggested_row']}, col={result['suggested_col']}")
        print(f"Coverage gain : {result['coverage_gain_pct']:.1f}%")
        print(f"Channel : {result['suggested_config']['channel']}")
        print(f"Explanation : {result['explanation'][:120]}...")
    except Exception as e:
        print("ERROR:", e)
    finally:
        client.close()