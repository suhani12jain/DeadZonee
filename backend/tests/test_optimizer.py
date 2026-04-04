# tests/test_optimizer.py
import numpy as np
import pytest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.ml_models.optimizer import (
    weighted_coverage_score,
    score_layout,
    optimise_layout,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture
def small_grid():
    # 5x5 grid of office cells, all allow_router, priority_weight 1.5
    return [{'row': r, 'col': c, 'zone_type': 'office',
              'attenuation': 6.0, 'priority_weight': 1.5, 'allow_router': True}
            for r in range(5) for c in range(5)]


@pytest.fixture
def good_signal():
    return np.full((5, 5), -60.0)   # well covered


@pytest.fixture
def dead_signal():
    return np.full((5, 5), -100.0)  # all dead


@pytest.fixture
def zero_interf():
    return np.zeros((5, 5))


@pytest.fixture
def zero_dead():
    return np.zeros((5, 5), dtype=bool)


@pytest.fixture
def full_dead():
    return np.ones((5, 5), dtype=bool)


@pytest.fixture
def two_routers():
    return [
        {'_id': 'r1', 'row': 1, 'col': 1, 'session_id': 'test',
         'tx_power_dbm': 20, 'frequency_mhz': 2400, 'channel': 1, 'range_m': 50},
        {'_id': 'r2', 'row': 3, 'col': 3, 'session_id': 'test',
         'tx_power_dbm': 20, 'frequency_mhz': 2400, 'channel': 6, 'range_m': 50},
    ]


def _mock_db(small_grid, two_routers):
    db = MagicMock()
    db.sessions.find_one.return_value = {
        '_id': 'test', 'grid_rows': 5, 'grid_cols': 5, 'cell_size_m': 2.0,
    }
    db.grids.find_one.return_value = {'session_id': 'test', 'cells': small_grid}
    db.signal_results.find_one.return_value = {
        'session_id': 'test',
        'signal_matrix':       np.full((5, 5), -75.0).tolist(),
        'interference_matrix': np.zeros((5, 5)).tolist(),
        'quality_matrix':      [['POOR']*5]*5,
        'metrics':             {'coverage_pct': 30.0},
    }
    db.deadzones.find_one.return_value = {
        'session_id':    'test',
        'dead_zone_mask': np.ones((5, 5), dtype=bool).tolist(),
        'dead_zone_count': 25,
        'clusters': [{'cluster_id': 0, 'size': 25,
                      'centroid_row': 2.0, 'centroid_col': 2.0}],
    }
    db.routers.find.return_value = iter(two_routers)
    db.optimisation_results.replace_one.return_value = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Tests: weighted_coverage_score
# ---------------------------------------------------------------------------
def test_coverage_perfect(small_grid, good_signal):
    assert weighted_coverage_score(good_signal, small_grid) == pytest.approx(100.0, abs=0.1)


def test_coverage_zero(small_grid, dead_signal):
    assert weighted_coverage_score(dead_signal, small_grid) == pytest.approx(0.0, abs=0.1)


def test_coverage_empty_cells():
    assert weighted_coverage_score(np.zeros((3, 3)), []) == 0.0


# ---------------------------------------------------------------------------
# Tests: score_layout
# ---------------------------------------------------------------------------
def test_score_good_beats_dead(small_grid, good_signal, dead_signal,
                                zero_interf, zero_dead, full_dead):
    pos = [{'row': 2, 'col': 2}]
    good = score_layout(pos, good_signal, zero_interf, zero_dead, small_grid)
    dead = score_layout(pos, dead_signal, zero_interf, full_dead, small_grid)
    assert good > dead


def test_score_no_zone_penalty(small_grid, good_signal, zero_interf, zero_dead):
    no_zone_cells = [{**c, 'allow_router': False, 'priority_weight': 0.0}
                     for c in small_grid]
    pos = [{'row': 2, 'col': 2}]
    score_allowed = score_layout(pos, good_signal, zero_interf, zero_dead, small_grid)
    score_blocked = score_layout(pos, good_signal, zero_interf, zero_dead, no_zone_cells)
    assert score_allowed > score_blocked


# ---------------------------------------------------------------------------
# Tests: optimise_layout (mock DB)
# ---------------------------------------------------------------------------
def test_returns_required_keys(small_grid, two_routers):
    db = _mock_db(small_grid, two_routers)
    result = optimise_layout('test', db)
    for key in ['algorithm', 'original_score', 'optimised_score',
                'improvement_pct', 'optimised_routers', 'score_history']:
        assert key in result, f"Missing: {key}"


def test_writes_to_mongodb(small_grid, two_routers):
    db = _mock_db(small_grid, two_routers)
    optimise_layout('test', db)
    db.optimisation_results.replace_one.assert_called_once()


def test_router_count_preserved(small_grid, two_routers):
    db = _mock_db(small_grid, two_routers)
    result = optimise_layout('test', db)
    assert len(result['optimised_routers']) == len(two_routers)


def test_algorithm_valid(small_grid, two_routers):
    db = _mock_db(small_grid, two_routers)
    result = optimise_layout('test', db)
    assert result['algorithm'] in ['PSO', 'SimulatedAnnealing']


def test_no_routers_raises(small_grid):
    db = _mock_db(small_grid, [])
    db.routers.find.return_value = iter([])
    with pytest.raises(ValueError, match="No routers"):
        optimise_layout('test', db)


def test_no_signal_raises(small_grid, two_routers):
    db = _mock_db(small_grid, two_routers)
    db.signal_results.find_one.return_value = None
    with pytest.raises(ValueError, match="analysis"):
        optimise_layout('test', db)