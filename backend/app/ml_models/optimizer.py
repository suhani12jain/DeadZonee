# backend/app/ml_models/optimizer.py
import os
import math
import random
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../../.env'))

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME   = os.getenv("DB_NAME", "deadzone01")

# ---------------------------------------------------------------------------
# WEIGHTED COVERAGE SCORE HELPER
# This is M1's function. Import from signal_engine when M1 pushes.
# Until then, use this local version (identical logic).
# At integration: replace with:
#   from app.ml_models.signal_engine import weighted_coverage_score
# ---------------------------------------------------------------------------
def weighted_coverage_score(signal_matrix, cells, threshold=-85.0):
    """Compute coverage weighted by zone priority.
    High-priority zones (office, server_room) count more than bathrooms."""
    total_weight   = 0.0
    covered_weight = 0.0
    for cell in cells:
        r  = cell['row']
        c  = cell['col']
        pw = float(cell.get('priority_weight', 0.0))
        total_weight += pw
        if pw > 0 and signal_matrix[r][c] > threshold:
            covered_weight += pw
    return (covered_weight / total_weight) * 100.0 if total_weight > 0 else 0.0


# ---------------------------------------------------------------------------
# SCORE FUNCTION
# Higher score = better layout.
# router_positions must be a list of dicts with 'row' and 'col' keys.
# Penalises: dead zones, interference, routers in blocked/no-zone cells.
# ---------------------------------------------------------------------------
def score_layout(router_positions, signal_matrix, interference_matrix,
                 dead_mask, grid_cells_flat):
    """Score a router layout. router_positions = [{'row': int, 'col': int}, ...]"""
    coverage  = weighted_coverage_score(signal_matrix, grid_cells_flat)
    interf    = float(np.mean(interference_matrix))
    dz_pen    = float(np.sum(dead_mask)) / dead_mask.size

    cell_map = {(c['row'], c['col']): c for c in grid_cells_flat}
    no_zone_pen = sum(
        1 for r in router_positions
        if not cell_map.get((r['row'], r['col']), {}).get('allow_router', True)
    )
    return coverage - interf - dz_pen - no_zone_pen * 5.0


# ---------------------------------------------------------------------------
# PSO — Particle Swarm Optimisation
# Each particle encodes the (row, col) of every router as a numpy array.
# Internally uses numpy arrays; converts to {'row', 'col'} dicts for scoring.
# ---------------------------------------------------------------------------
def _pso(routers, grid_rows, grid_cols, signal_matrix, interference_matrix,
         dead_mask, grid_cells_flat, n_particles=15, n_iter=40):
    n_routers = len(routers)
    if n_routers == 0:
        return [], []

    particles  = [np.array([[random.randint(0, grid_rows - 1),
                              random.randint(0, grid_cols - 1)]
                             for _ in range(n_routers)], dtype=float)
                  for _ in range(n_particles)]
    velocities = [np.zeros((n_routers, 2)) for _ in range(n_particles)]
    pbest      = [p.copy() for p in particles]

    def particle_score(pos_arr):
        # pos_arr shape: (n_routers, 2) — always uses 'row'/'col' keys
        pos_list = [{'row': int(pos_arr[i, 0]), 'col': int(pos_arr[i, 1])}
                    for i in range(n_routers)]
        return score_layout(pos_list, signal_matrix, interference_matrix,
                            dead_mask, grid_cells_flat)

    pbest_scores = [particle_score(p) for p in particles]
    gbest_idx    = int(np.argmax(pbest_scores))
    gbest        = pbest[gbest_idx].copy()
    gbest_score  = pbest_scores[gbest_idx]

    w, c1, c2 = 0.7, 1.5, 1.5
    score_history = [gbest_score]

    for _ in range(n_iter):
        for i in range(n_particles):
            r1 = np.random.rand(n_routers, 2)
            r2 = np.random.rand(n_routers, 2)
            velocities[i] = (w * velocities[i]
                             + c1 * r1 * (pbest[i] - particles[i])
                             + c2 * r2 * (gbest    - particles[i]))
            particles[i] = particles[i] + velocities[i]
            particles[i][:, 0] = np.clip(particles[i][:, 0], 0, grid_rows - 1)
            particles[i][:, 1] = np.clip(particles[i][:, 1], 0, grid_cols - 1)

            s = particle_score(particles[i])
            if s > pbest_scores[i]:
                pbest[i]        = particles[i].copy()
                pbest_scores[i] = s
                if s > gbest_score:
                    gbest       = particles[i].copy()
                    gbest_score = s

        score_history.append(gbest_score)

    best_positions = [
        {
            'router_id': str(routers[i].get('_id', '')),
            'new_row':   int(round(gbest[i, 0])),
            'new_col':   int(round(gbest[i, 1])),
        }
        for i in range(n_routers)
    ]
    return best_positions, score_history


# ---------------------------------------------------------------------------
# SIMULATED ANNEALING
# Internally works with {'row', 'col'} dicts throughout — consistent with
# score_layout's expected format. Output is converted to 'new_row'/'new_col'
# only at the very end, after all scoring is done.
# ---------------------------------------------------------------------------
def _sa(routers, grid_rows, grid_cols, signal_matrix, interference_matrix,
        dead_mask, grid_cells_flat, t_start=500.0, cooling=0.92, n_steps=200):
    n_routers = len(routers)
    if n_routers == 0:
        return [], []

    # FIX: use 'row'/'col' keys internally so score_layout can read them
    current = [{'row': r['row'], 'col': r['col']} for r in routers]

    def pos_score(pos_list):
        # pos_list is always [{'row': int, 'col': int}, ...] — matches score_layout
        return score_layout(pos_list, signal_matrix, interference_matrix,
                            dead_mask, grid_cells_flat)

    current_score = pos_score(current)
    best          = [p.copy() for p in current]
    best_score    = current_score
    T             = t_start
    score_history = [current_score]

    for step in range(n_steps):
        idx     = random.randint(0, n_routers - 1)
        delta_r = random.randint(-5, 5)
        delta_c = random.randint(-5, 5)

        # FIX: copy dicts properly and use 'row'/'col' keys throughout
        candidate = [p.copy() for p in current]
        candidate[idx]['row'] = max(0, min(grid_rows - 1,
                                           candidate[idx]['row'] + delta_r))
        candidate[idx]['col'] = max(0, min(grid_cols - 1,
                                           candidate[idx]['col'] + delta_c))

        new_score = pos_score(candidate)
        delta     = new_score - current_score

        if delta > 0 or random.random() < math.exp(delta / T):
            current       = candidate
            current_score = new_score
            if new_score > best_score:
                best       = [p.copy() for p in candidate]
                best_score = new_score

        T *= cooling
        if step % 20 == 0:
            score_history.append(best_score)

    score_history.append(best_score)

    # Convert to output format ('new_row'/'new_col') only here at the end
    best_positions = [
        {
            'router_id': str(routers[i].get('_id', '')),
            'new_row':   best[i]['row'],
            'new_col':   best[i]['col'],
        }
        for i in range(n_routers)
    ]
    return best_positions, score_history


# ---------------------------------------------------------------------------
# MAIN ENTRYPOINT — called by M3's FastAPI route
# ---------------------------------------------------------------------------
def optimise_layout(session_id: str, db) -> dict:
    # 1. Read session metadata
    session = db.sessions.find_one({'session_id': session_id})
    if not session:
        raise ValueError(f"Session {session_id} not found in MongoDB")

    grid_rows = session['grid_rows']
    grid_cols = session['grid_cols']

    # 2. Read grid cells
    grid_doc = db.grids.find_one({'session_id': session_id})
    if not grid_doc:
        raise ValueError(f"Grid not found for session {session_id}")
    grid_cells_flat = grid_doc['cells']

    # 3. Read signal results
    sig_doc = db.signal_results.find_one({'session_id': session_id})
    if not sig_doc:
        raise ValueError("Run analysis (signal engine) before optimising")

    signal_matrix       = np.array(sig_doc['signal_matrix'],       dtype=float)
    interference_matrix = np.array(sig_doc['interference_matrix'], dtype=float)

    # 4. Read dead zones
    dz_doc = db.deadzones.find_one({'session_id': session_id})
    if not dz_doc:
        raise ValueError("Run analysis (dead zone detector) before optimising")
    dead_mask = np.array(dz_doc['dead_zone_mask'], dtype=bool)

    # 5. Read routers
    routers = list(db.routers.find({'session_id': session_id}))
    if not routers:
        raise ValueError("No routers found. Place at least one router first.")

    # 6. Compute baseline score using 'row'/'col' keys — same format as score_layout expects
    original_positions = [{'row': r['row'], 'col': r['col']} for r in routers]
    original_score     = score_layout(original_positions, signal_matrix,
                                      interference_matrix, dead_mask, grid_cells_flat)

    # 7. Run PSO
    pso_positions, pso_history = _pso(
        routers, grid_rows, grid_cols,
        signal_matrix, interference_matrix, dead_mask, grid_cells_flat,
        n_particles=15, n_iter=40)
    pso_score = pso_history[-1] if pso_history else original_score

    # 8. Run SA
    sa_positions, sa_history = _sa(
        routers, grid_rows, grid_cols,
        signal_matrix, interference_matrix, dead_mask, grid_cells_flat,
        t_start=500.0, cooling=0.92, n_steps=200)
    sa_score = sa_history[-1] if sa_history else original_score

    # 9. Pick winner
    if pso_score >= sa_score:
        winner_algo, winner_positions = 'PSO', pso_positions
        winner_score, winner_history  = pso_score, pso_history
    else:
        winner_algo, winner_positions = 'SimulatedAnnealing', sa_positions
        winner_score, winner_history  = sa_score, sa_history

    improvement_pct = ((winner_score - original_score) / abs(original_score) * 100.0
                       if original_score != 0 else 0.0)

    # 10. Write to MongoDB
    result_doc = {
        'session_id':        session_id,
        'algorithm':         winner_algo,
        'original_score':    float(original_score),
        'optimised_score':   float(winner_score),
        'improvement_pct':   float(improvement_pct),
        'optimised_routers': winner_positions,
        'score_history':     [float(s) for s in winner_history],
    }
    db.optimisation_results.replace_one(
        {'session_id': session_id}, result_doc, upsert=True)
    return result_doc


# ---------------------------------------------------------------------------
# STANDALONE TEST — python3 backend/app/ml_models/optimizer.py <session_id>
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python optimizer.py <session_id>")
        sys.exit(1)
    session_id = sys.argv[1]
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        result = optimise_layout(session_id, db)
        print("Algorithm   :", result['algorithm'])
        print("Before score:", result['original_score'])
        print("After score :", result['optimised_score'])
        print("Improvement :", f"{result['improvement_pct']:.1f}%")
        print("Routers moved:", len(result['optimised_routers']))
    except Exception as e:
        print("ERROR:", e)
    finally:
        client.close()