# backend/app/ml_models/optimizer.py
import os
import math
import random
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env"))

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "deadzone01")

DEAD_THRESHOLD_DBM = -85.0
INTERFERENCE_MARGIN = -67.0
ADJACENT_CHANNELS_24 = 5
ADJACENT_CHANNELS_5 = 4
MIN_DISTANCE_M = 0.1
MIN_ROUTER_SEPARATION = 3
NO_CHANGE_EPSILON = 0.25


def _build_allowed_cells(grid_cells_flat):
    allowed = [
        {"row": int(cell["row"]), "col": int(cell["col"])}
        for cell in grid_cells_flat
        if cell.get("allow_router", True)
    ]
    return allowed or [
        {"row": int(cell["row"]), "col": int(cell["col"])}
        for cell in grid_cells_flat
    ]


def _snap_to_allowed(row, col, allowed_cells):
    best = allowed_cells[0]
    best_dist = None
    for cell in allowed_cells:
        dr = cell["row"] - row
        dc = cell["col"] - col
        dist = dr * dr + dc * dc
        if best_dist is None or dist < best_dist:
            best = cell
            best_dist = dist
    return {"row": int(best["row"]), "col": int(best["col"])}


def _sim_signal(candidate_positions, router_templates,
                attn_matrix, cell_x, cell_y, cell_size_m):
    rows, cols = attn_matrix.shape
    best_signal = np.full((rows, cols), -200.0, dtype=np.float64)
    signals = []

    for i, pos in enumerate(candidate_positions):
        tmpl = router_templates[i]
        tx_power = float(tmpl.get("tx_power_dbm", 20.0))
        freq_mhz = float(tmpl.get("frequency_mhz", 2400.0))
        range_m = float(tmpl.get("range_m", 50.0))

        router_x = pos["col"] * cell_size_m + cell_size_m / 2.0
        router_y = pos["row"] * cell_size_m + cell_size_m / 2.0

        dx = cell_x - router_x
        dy = cell_y - router_y
        distance = np.sqrt(dx ** 2 + dy ** 2)
        distance = np.maximum(distance, MIN_DISTANCE_M)

        path_loss = 20.0 * np.log10(distance) + 20.0 * np.log10(freq_mhz) - 27.55
        received = tx_power - path_loss - attn_matrix
        received[distance > range_m] = -200.0

        best_signal = np.maximum(best_signal, received)
        signals.append(received)

    interference = np.zeros((rows, cols), dtype=np.float64)
    n = len(router_templates)
    for i in range(n):
        for j in range(i + 1, n):
            ch_a = int(router_templates[i].get("channel", 1))
            ch_b = int(router_templates[j].get("channel", 1))
            freq_a = float(router_templates[i].get("frequency_mhz", 2400.0))
            if ch_a == ch_b:
                overlaps = True
            elif freq_a < 3000:
                overlaps = abs(ch_a - ch_b) < ADJACENT_CHANNELS_24
            else:
                overlaps = abs(ch_a - ch_b) < ADJACENT_CHANNELS_5
            if overlaps:
                both = (signals[i] > INTERFERENCE_MARGIN) & (signals[j] > INTERFERENCE_MARGIN)
                interference += both.astype(np.float64)

    max_val = interference.max()
    if max_val > 0:
        interference /= max_val

    return best_signal, interference


def _weighted_coverage(signal_matrix, grid_cells_flat):
    total_weight = 0.0
    covered_weight = 0.0
    for cell in grid_cells_flat:
        pw = float(cell.get("priority_weight", 0.0))
        total_weight += pw
        if pw > 0 and signal_matrix[cell["row"], cell["col"]] > DEAD_THRESHOLD_DBM:
            covered_weight += pw
    return (covered_weight / total_weight * 100.0) if total_weight > 0 else 0.0


def _score(candidate_positions, router_templates,
           attn_matrix, cell_x, cell_y, cell_size_m, grid_cells_flat):
    sig, interf = _sim_signal(candidate_positions, router_templates, attn_matrix, cell_x, cell_y, cell_size_m)
    coverage = _weighted_coverage(sig, grid_cells_flat)
    interf_p = float(np.mean(interf))
    dz_pen = float(np.sum(sig <= DEAD_THRESHOLD_DBM)) / sig.size

    cell_map = {(c["row"], c["col"]): c for c in grid_cells_flat}
    no_zone_pen = sum(
        1 for p in candidate_positions
        if not cell_map.get((p["row"], p["col"]), {}).get("allow_router", True)
    )

    proximity_pen = 0.0
    n = len(candidate_positions)
    for i in range(n):
        for j in range(i + 1, n):
            dr = candidate_positions[i]["row"] - candidate_positions[j]["row"]
            dc = candidate_positions[i]["col"] - candidate_positions[j]["col"]
            dist = math.sqrt(dr * dr + dc * dc)
            if dist < MIN_ROUTER_SEPARATION:
                proximity_pen += 10.0

    return coverage - interf_p - dz_pen - no_zone_pen * 5.0 - proximity_pen


def _pso(routers, grid_rows, grid_cols,
         attn_matrix, cell_x, cell_y, cell_size_m,
         grid_cells_flat, allowed_cells, n_particles=15, n_iter=40):
    n_routers = len(routers)
    if n_routers == 0:
        return [], []

    def score_arr(pos_arr):
        pos_list = [
            _snap_to_allowed(
                int(np.clip(pos_arr[i, 0], 0, grid_rows - 1)),
                int(np.clip(pos_arr[i, 1], 0, grid_cols - 1)),
                allowed_cells,
            )
            for i in range(n_routers)
        ]
        return _score(pos_list, routers, attn_matrix, cell_x, cell_y, cell_size_m, grid_cells_flat)

    current_pos = np.array([[r["row"], r["col"]] for r in routers], dtype=float)
    particles = [current_pos.copy()] + [
        np.array([
            [random.choice(allowed_cells)["row"], random.choice(allowed_cells)["col"]]
            for _ in range(n_routers)
        ], dtype=float)
        for _ in range(n_particles - 1)
    ]

    velocities = [np.zeros((n_routers, 2)) for _ in range(n_particles)]
    pbest = [p.copy() for p in particles]
    pbest_sc = [score_arr(p) for p in particles]
    gbest_idx = int(np.argmax(pbest_sc))
    gbest = pbest[gbest_idx].copy()
    gbest_sc = pbest_sc[gbest_idx]

    w, c1, c2 = 0.7, 1.5, 1.5
    score_history = [gbest_sc]

    for _ in range(n_iter):
        for i in range(n_particles):
            r1 = np.random.rand(n_routers, 2)
            r2 = np.random.rand(n_routers, 2)
            velocities[i] = (
                w * velocities[i]
                + c1 * r1 * (pbest[i] - particles[i])
                + c2 * r2 * (gbest - particles[i])
            )
            particles[i] += velocities[i]
            particles[i][:, 0] = np.clip(particles[i][:, 0], 0, grid_rows - 1)
            particles[i][:, 1] = np.clip(particles[i][:, 1], 0, grid_cols - 1)

            s = score_arr(particles[i])
            if s > pbest_sc[i]:
                pbest[i] = particles[i].copy()
                pbest_sc[i] = s
                if s > gbest_sc:
                    gbest = particles[i].copy()
                    gbest_sc = s

        score_history.append(gbest_sc)

    best_positions = []
    for i in range(n_routers):
        snapped = _snap_to_allowed(
            int(round(np.clip(gbest[i, 0], 0, grid_rows - 1))),
            int(round(np.clip(gbest[i, 1], 0, grid_cols - 1))),
            allowed_cells,
        )
        best_positions.append({
            "router_id": str(routers[i].get("_id", "")),
            "new_row": snapped["row"],
            "new_col": snapped["col"],
        })

    return best_positions, score_history


def _sa(routers, grid_rows, grid_cols,
        attn_matrix, cell_x, cell_y, cell_size_m,
        grid_cells_flat, allowed_cells, t_start=500.0, cooling=0.92, n_steps=200):
    n_routers = len(routers)
    if n_routers == 0:
        return [], []

    current = [{"row": r["row"], "col": r["col"]} for r in routers]

    def pos_score(pos_list):
        return _score(pos_list, routers, attn_matrix, cell_x, cell_y, cell_size_m, grid_cells_flat)

    current_sc = pos_score(current)
    best = [p.copy() for p in current]
    best_sc = current_sc
    temperature = t_start
    score_history = [current_sc]

    for step in range(n_steps):
        idx = random.randint(0, n_routers - 1)
        candidate = [p.copy() for p in current]
        target = random.choice(allowed_cells)
        candidate[idx] = {"row": target["row"], "col": target["col"]}

        new_sc = pos_score(candidate)
        delta = new_sc - current_sc

        if delta > 0 or random.random() < math.exp(delta / temperature):
            current = candidate
            current_sc = new_sc
            if new_sc > best_sc:
                best = [p.copy() for p in candidate]
                best_sc = new_sc

        temperature *= cooling
        if step % 20 == 0:
            score_history.append(best_sc)

    score_history.append(best_sc)

    best_positions = []
    for i in range(n_routers):
        snapped = _snap_to_allowed(best[i]["row"], best[i]["col"], allowed_cells)
        best_positions.append({
            "router_id": str(routers[i].get("_id", "")),
            "new_row": snapped["row"],
            "new_col": snapped["col"],
        })

    return best_positions, score_history


def optimise_layout(session_id: str, db) -> dict:
    sid = session_id

    session = db.sessions.find_one({"session_id": sid})
    if not session:
        raise ValueError(f"Session {sid} not found. Check the session_id.")
    grid_rows = int(session["grid_rows"])
    grid_cols = int(session["grid_cols"])
    cell_size_m = float(session["cell_size_m"])

    grid_doc = db.grids.find_one({"session_id": sid})
    if not grid_doc:
        raise ValueError(f"Grid not found for session {sid}.")
    grid_cells_flat = grid_doc["cells"]
    allowed_cells = _build_allowed_cells(grid_cells_flat)

    routers = list(db.routers.find({"session_id": sid}))
    if not routers:
        raise ValueError("No routers found. Place at least one router first.")

    from app.ml_models.signal_engine import _build_attenuation_matrix, _build_coord_arrays

    attn_matrix = _build_attenuation_matrix(grid_cells_flat, grid_rows, grid_cols)
    cell_x, cell_y = _build_coord_arrays(grid_cells_flat, cell_size_m, grid_rows, grid_cols)

    original_positions = [{"row": r["row"], "col": r["col"]} for r in routers]
    original_score = _score(original_positions, routers, attn_matrix, cell_x, cell_y, cell_size_m, grid_cells_flat)

    pso_positions, pso_history = _pso(
        routers, grid_rows, grid_cols, attn_matrix, cell_x, cell_y,
        cell_size_m, grid_cells_flat, allowed_cells, n_particles=15, n_iter=40,
    )
    pso_score = pso_history[-1] if pso_history else original_score

    sa_positions, sa_history = _sa(
        routers, grid_rows, grid_cols, attn_matrix, cell_x, cell_y,
        cell_size_m, grid_cells_flat, allowed_cells, t_start=500.0, cooling=0.92, n_steps=200,
    )
    sa_score = sa_history[-1] if sa_history else original_score

    if pso_score >= sa_score:
        winner_algo, winner_positions = "PSO", pso_positions
        winner_score, winner_history = pso_score, pso_history
    else:
        winner_algo, winner_positions = "SimulatedAnnealing", sa_positions
        winner_score, winner_history = sa_score, sa_history

    improvement_pct = ((winner_score - original_score) / abs(original_score) * 100.0) if original_score != 0 else 0.0
    changed_positions = any(
        pos["new_row"] != router["row"] or pos["new_col"] != router["col"]
        for pos, router in zip(winner_positions, routers)
    )
    no_change_required = (winner_score - original_score) <= NO_CHANGE_EPSILON or not changed_positions

    if no_change_required:
        winner_positions = [
            {
                "router_id": str(router.get("_id", "")),
                "new_row": int(router["row"]),
                "new_col": int(router["col"]),
            }
            for router in routers
        ]
        winner_score = original_score
        improvement_pct = 0.0

    result_doc = {
        "session_id": sid,
        "algorithm": winner_algo,
        "original_score": float(original_score),
        "optimised_score": float(winner_score),
        "improvement_pct": float(improvement_pct),
        "optimised_routers": winner_positions,
        "score_history": [float(s) for s in winner_history],
        "no_change_required": no_change_required,
        "message": (
            "Current router placement is already strong enough that no move is justified."
            if no_change_required
            else f"{winner_algo} found a stronger router layout and updated coordinates."
        ),
    }
    db.optimisation_results.replace_one({"session_id": sid}, result_doc, upsert=True)

    from bson import ObjectId

    if not no_change_required:
        for pos in winner_positions:
            try:
                router_oid = ObjectId(pos["router_id"])
            except Exception:
                continue
            db.routers.update_one(
                {"_id": router_oid},
                {"$set": {"row": pos["new_row"], "col": pos["new_col"]}},
            )

    return result_doc


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python optimizer.py <session_id>")
        sys.exit(1)
    sid = sys.argv[1]
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        result = optimise_layout(sid, db)
        print("Algorithm   :", result["algorithm"])
        print("Before score:", result["original_score"])
        print("After score :", result["optimised_score"])
        print("Improvement :", f"{result['improvement_pct']:.1f}%")
        print("Message     :", result["message"])
        for router in result["optimised_routers"]:
            print(f"  {router['router_id']} -> row={router['new_row']} col={router['new_col']}")
    except Exception as e:
        print("ERROR:", e)
        import traceback
        traceback.print_exc()
    finally:
        client.close()
