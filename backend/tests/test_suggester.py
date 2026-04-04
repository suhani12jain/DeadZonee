# tests/test_suggester.py
import numpy as np
import pytest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.ml_models.placement_suggester import (
    suggest_placement,
    _spiral_find_valid_cell,
    _pick_channel,
    _estimate_coverage_gain,
    _call_claude,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture
def office_cells():
    return [{'row': r, 'col': c, 'zone_type': 'office',
              'attenuation': 6.0, 'priority_weight': 1.5, 'allow_router': True}
            for r in range(5) for c in range(5)]


@pytest.fixture
def cell_map_all_allowed(office_cells):
    return {(c['row'], c['col']): c for c in office_cells}


@pytest.fixture
def cell_map_center_blocked(office_cells):
    cmap = {(c['row'], c['col']): c for c in office_cells}
    for r in range(1, 4):
        for c in range(1, 4):
            cmap[(r, c)] = {**cmap[(r, c)], 'allow_router': False}
    return cmap


@pytest.fixture
def clusters_one():
    return [{'cluster_id': 0, 'size': 10,
              'centroid_row': 2.0, 'centroid_col': 2.0, 'cells': []}]


@pytest.fixture
def mock_db(office_cells, clusters_one):
    db = MagicMock()
    db.sessions.find_one.return_value = {
        '_id': 'sess1', 'grid_rows': 5, 'grid_cols': 5, 'cell_size_m': 2.0,
    }
    db.deadzones.find_one.return_value = {
        'session_id': 'sess1',
        'dead_zone_mask': np.ones((5, 5), dtype=bool).tolist(),
        'dead_zone_count': 25,
        'clusters': clusters_one,
    }
    db.grids.find_one.return_value = {'session_id': 'sess1', 'cells': office_cells}
    db.routers.find.return_value = iter([])
    db.signal_results.find_one.return_value = {
        'signal_matrix': np.full((5, 5), -100.0).tolist(),
    }
    db.suggestions.insert_one.return_value = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Tests: _spiral_find_valid_cell
# ---------------------------------------------------------------------------
def test_spiral_returns_centroid_when_allowed(cell_map_all_allowed):
    r, c = _spiral_find_valid_cell(2, 2, cell_map_all_allowed, 5, 5)
    assert (r, c) == (2, 2)


def test_spiral_finds_outer_when_blocked(cell_map_center_blocked):
    r, c = _spiral_find_valid_cell(2, 2, cell_map_center_blocked, 5, 5)
    cell = cell_map_center_blocked.get((r, c), {})
    assert cell.get('allow_router', False), f"({r},{c}) must be allow_router=True"


def test_spiral_in_bounds():
    cmap = {(0, 0): {'allow_router': True}}
    r, c = _spiral_find_valid_cell(0, 0, cmap, 5, 5)
    assert 0 <= r < 5 and 0 <= c < 5


# ---------------------------------------------------------------------------
# Tests: _pick_channel
# ---------------------------------------------------------------------------
def test_channel_no_routers():
    ch = _pick_channel([], 2400, 2, 2, 2.0, 50)
    assert ch in [1, 6, 11]


def test_channel_avoids_used():
    routers = [{'row': 2, 'col': 2, 'channel': 1, 'frequency_mhz': 2400}] * 3
    ch = _pick_channel(routers, 2400, 2, 2, 2.0, 50)
    assert ch in [6, 11]


def test_channel_5ghz():
    assert _pick_channel([], 5000, 2, 2, 2.0, 50) in [36, 40, 44, 48, 149, 153, 157, 161]


# ---------------------------------------------------------------------------
# Tests: _estimate_coverage_gain
# ---------------------------------------------------------------------------
def test_gain_all_dead():
    dead = np.ones((5, 5), dtype=bool)
    gain = _estimate_coverage_gain(None, dead, 2, 2, 2, 5, 5)
    assert gain > 0.0


def test_gain_none_dead():
    dead = np.zeros((5, 5), dtype=bool)
    gain = _estimate_coverage_gain(None, dead, 2, 2, 2, 5, 5)
    assert gain == 0.0


# ---------------------------------------------------------------------------
# Tests: _call_claude
# ---------------------------------------------------------------------------
def test_claude_no_key_returns_string():
    result = _call_claude(10, 2, 3, 'office', 1.5, 6, 2400, api_key='')
    assert isinstance(result, str) and len(result) > 20


def test_claude_bad_key_returns_fallback():
    result = _call_claude(10, 2, 3, 'corridor', 0.8, 1, 2400, api_key='bad_key_xyz')
    assert isinstance(result, str) and len(result) > 20


# ---------------------------------------------------------------------------
# Tests: suggest_placement (mock DB)
# ---------------------------------------------------------------------------
def test_suggest_required_keys(mock_db):
    result = suggest_placement('sess1', mock_db, anthropic_key='')
    for key in ['suggested_row', 'suggested_col', 'suggested_config',
                'explanation', 'coverage_gain_pct', 'accepted']:
        assert key in result


def test_suggest_allow_router_true(mock_db, office_cells):
    result = suggest_placement('sess1', mock_db, anthropic_key='')
    cell_map = {(c['row'], c['col']): c for c in office_cells}
    cell = cell_map.get((result['suggested_row'], result['suggested_col']), {})
    assert cell.get('allow_router', False)


def test_suggest_writes_mongodb(mock_db):
    suggest_placement('sess1', mock_db, anthropic_key='')
    mock_db.suggestions.insert_one.assert_called_once()


def test_suggest_config_fields(mock_db):
    result = suggest_placement('sess1', mock_db, anthropic_key='')
    for f in ['tx_power', 'frequency', 'channel', 'range']:
        assert f in result['suggested_config']


def test_suggest_channel_valid(mock_db):
    result = suggest_placement('sess1', mock_db, anthropic_key='')
    assert result['suggested_config']['channel'] in [1,6,11,36,40,44,48,149,153,157,161]


def test_suggest_no_clusters_raises(mock_db):
    mock_db.deadzones.find_one.return_value = {
        'session_id': 'sess1', 'dead_zone_mask': [],
        'dead_zone_count': 0, 'clusters': []
    }
    with pytest.raises(ValueError, match="clusters"):
        suggest_placement('sess1', mock_db, anthropic_key='')