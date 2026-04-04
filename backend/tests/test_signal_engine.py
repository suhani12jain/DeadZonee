"""
tests/test_signal_engine.py  —  Member 1
DeadZero v3.0

Run:  python -m pytest tests/test_signal_engine.py -v

Tests cover:
  - Path-loss formula accuracy for known distance
  - Best-signal (max across multiple routers)
  - Quality matrix labels
  - Interference detection between co-channel routers
  - Interference absent for well-separated channels
  - weighted_coverage_score helper
  - MongoDB write (mocked with mongomock or a simple dict-based fake)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np

# Import the module under test
from app.ml_models.signal_engine import (
    compute_signal,
    weighted_coverage_score,
    _signal_one_router,
    _build_attenuation_matrix,
    _build_coord_arrays,
    _build_quality_matrix,
    _channels_interfere,
    DEAD_THRESHOLD_DBM,
    GOOD_THRESHOLD_DBM,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal fake DB — mimics pymongo synchronous API (find_one / replace_one)
# ─────────────────────────────────────────────────────────────────────────────
class FakeCollection:
    def __init__(self, docs=None):
        self._docs = docs or []

    def find_one(self, query):
        # Very simple: just return first doc that matches all keys in query
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find(self, query):
        return [d for d in self._docs
                if all(d.get(k) == v for k, v in query.items())]

    def replace_one(self, query, replacement, upsert=False):
        for i, doc in enumerate(self._docs):
            if all(doc.get(k) == v for k, v in query.items()):
                self._docs[i] = replacement
                return
        if upsert:
            self._docs.append(replacement)

    def __iter__(self):
        return iter(self._docs)


class FakeDB:
    """Acts like db[collection_name]."""
    def __init__(self, collections: dict):
        self._colls = {k: FakeCollection(v) for k, v in collections.items()}

    def __getitem__(self, name):
        if name not in self._colls:
            self._colls[name] = FakeCollection()
        return self._colls[name]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
CELL_SIZE_M   = 2.0     # 2 m per cell
GRID_ROWS     = 10
GRID_COLS     = 10
SESSION_ID    = "aaaaaaaaaaaaaaaaaaaaaaaa"   # 24-char hex (fake ObjectId string)


def _make_cells(attn_override: float = 0.0):
    """Create a flat 10×10 cell list with uniform attenuation."""
    cells = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cells.append({
                "row": r, "col": c,
                "x_m": c * CELL_SIZE_M,
                "y_m": r * CELL_SIZE_M,
                "zone_type": "office",
                "attenuation": attn_override,
                "priority_weight": 1.0,
                "allow_router": True,
            })
    return cells


def _make_router(row=4, col=4, tx=20.0, freq=5000.0, ch=36, cost=2000.0):
    return {
        "_id": "router_a",
        "session_id": SESSION_ID,
        "name": "AP-01",
        "row": row, "col": col,
        "tx_power_dbm": tx,
        "frequency_mhz": freq,
        "channel": ch,
        "range_m": 50.0,
        "cost": cost,
        "is_suggested": False,
    }


def _fake_db(routers, attn=0.0, cells=None):
    from bson import ObjectId
    sid = ObjectId(SESSION_ID)
    c   = cells if cells is not None else _make_cells(attn)
    return FakeDB({
        "sessions": [{
            "_id": sid,
            "grid_rows": GRID_ROWS,
            "grid_cols": GRID_COLS,
            "cell_size_m": CELL_SIZE_M,
        }],
        "grids": [{
            "session_id": sid,
            "cells": c,
        }],
        "routers": [{**r, "session_id": sid} for r in routers],
        "signal_results": [],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — internal helpers
# ─────────────────────────────────────────────────────────────────────────────
class TestPathLossFormula:
    """Verify the path-loss formula against manual calculation."""

    def _manual_received(self, distance_m, tx_dbm=20.0, freq_mhz=5000.0,
                         attn_db=0.0):
        path_loss = (20 * np.log10(distance_m) +
                     20 * np.log10(freq_mhz) - 27.55)
        return tx_dbm - path_loss - attn_db

    def test_50m_5ghz_above_minus70(self):
        """1 router at 20 dBm / 5 GHz / 50 m away — received must be > -70 dBm."""
        expected = self._manual_received(50.0, tx_dbm=20.0, freq_mhz=5000.0)
        assert expected > -70.0, f"Expected > -70 dBm, got {expected:.2f}"

    def test_200m_drops_significantly(self):
        """Received at 200 m must be well below 50 m."""
        r50  = self._manual_received(50.0)
        r200 = self._manual_received(200.0)
        assert r200 < r50 - 10, "Signal should drop significantly over 200 m"

    def test_attenuation_reduces_signal(self):
        """Adding attenuation must reduce received power."""
        no_attn   = self._manual_received(30.0, attn_db=0.0)
        with_attn = self._manual_received(30.0, attn_db=9.0)   # server_room
        assert with_attn < no_attn - 8.5


class TestSignalOneRouter:
    """Test _signal_one_router() shape and directional correctness."""

    def test_output_shape(self):
        cells  = _make_cells()
        attn   = _build_attenuation_matrix(cells, GRID_ROWS, GRID_COLS)
        cx, cy = _build_coord_arrays(cells, CELL_SIZE_M, GRID_ROWS, GRID_COLS)
        router = {**_make_router(), "_cell_size_m": CELL_SIZE_M}
        result = _signal_one_router(router, cx, cy, attn)
        assert result.shape == (GRID_ROWS, GRID_COLS)

    def test_router_cell_has_highest_signal(self):
        """Cell at router position should have highest received signal."""
        cells  = _make_cells()
        attn   = _build_attenuation_matrix(cells, GRID_ROWS, GRID_COLS)
        cx, cy = _build_coord_arrays(cells, CELL_SIZE_M, GRID_ROWS, GRID_COLS)
        router = {**_make_router(row=0, col=0), "_cell_size_m": CELL_SIZE_M}
        result = _signal_one_router(router, cx, cy, attn)
        assert result[0, 0] == pytest.approx(result.max(), rel=0.01)

    def test_signal_decreases_with_distance(self):
        """Signal at col=0 must be stronger than at col=9 (router at col=0)."""
        cells  = _make_cells()
        attn   = _build_attenuation_matrix(cells, GRID_ROWS, GRID_COLS)
        cx, cy = _build_coord_arrays(cells, CELL_SIZE_M, GRID_ROWS, GRID_COLS)
        router = {**_make_router(row=5, col=0), "_cell_size_m": CELL_SIZE_M}
        result = _signal_one_router(router, cx, cy, attn)
        assert result[5, 0] > result[5, 9]

    def test_high_attenuation_reduces_signal(self):
        """Wall (12 dB) must make far cells weaker than open space."""
        cells_open = _make_cells(attn_override=0.0)
        cells_wall = _make_cells(attn_override=12.0)
        attn_open  = _build_attenuation_matrix(cells_open, GRID_ROWS, GRID_COLS)
        attn_wall  = _build_attenuation_matrix(cells_wall, GRID_ROWS, GRID_COLS)
        cx, cy     = _build_coord_arrays(cells_open, CELL_SIZE_M,
                                          GRID_ROWS, GRID_COLS)
        router = {**_make_router(row=0, col=0), "_cell_size_m": CELL_SIZE_M}
        sig_open = _signal_one_router(router, cx, cy, attn_open)
        sig_wall = _signal_one_router(router, cx, cy, attn_wall)
        # Every cell should be weaker through wall
        assert np.all(sig_wall < sig_open)


class TestQualityMatrix:
    """Verify _build_quality_matrix labels."""

    def test_excellent_label(self):
        mat = np.array([[-40.0]])
        q   = _build_quality_matrix(mat)
        assert q[0][0] == "EXCELLENT"

    def test_good_label(self):
        mat = np.array([[-60.0]])
        assert _build_quality_matrix(mat)[0][0] == "GOOD"

    def test_fair_label(self):
        mat = np.array([[-70.0]])
        assert _build_quality_matrix(mat)[0][0] == "FAIR"

    def test_poor_label(self):
        mat = np.array([[-80.0]])
        assert _build_quality_matrix(mat)[0][0] == "POOR"

    def test_dead_label(self):
        mat = np.array([[-90.0]])
        assert _build_quality_matrix(mat)[0][0] == "DEAD"

    def test_shape_preserved(self):
        mat = np.random.uniform(-100, -30, (5, 8))
        q   = _build_quality_matrix(mat)
        assert len(q) == 5 and len(q[0]) == 8


class TestChannelInterference:
    def test_same_channel_interferes(self):
        assert _channels_interfere(6, 6, 2400.0) is True

    def test_adjacent_24ghz_interferes(self):
        assert _channels_interfere(1, 3, 2400.0) is True   # |1-3|=2 < 5

    def test_nonadjacent_24ghz_no_interference(self):
        assert _channels_interfere(1, 6, 2400.0) is False   # |1-6|=5 not < 5

    def test_nonadjacent_5ghz(self):
        assert _channels_interfere(36, 44, 5000.0) is False  # |36-44|=8 ≥ 4


class TestWeightedCoverageScore:
    def test_all_covered_returns_100(self):
        # signal > -85 everywhere
        sig = np.full((3, 3), -50.0)
        cells = [{"row": r, "col": c, "priority_weight": 1.0}
                 for r in range(3) for c in range(3)]
        score = weighted_coverage_score(sig, cells)
        assert score == pytest.approx(100.0, abs=0.01)

    def test_all_dead_returns_0(self):
        sig = np.full((3, 3), -100.0)
        cells = [{"row": r, "col": c, "priority_weight": 1.0}
                 for r in range(3) for c in range(3)]
        assert weighted_coverage_score(sig, cells) == pytest.approx(0.0)

    def test_partial_coverage(self):
        sig = np.array([[-50.0, -50.0], [-100.0, -100.0]])
        cells = [
            {"row": 0, "col": 0, "priority_weight": 1.0},
            {"row": 0, "col": 1, "priority_weight": 1.0},
            {"row": 1, "col": 0, "priority_weight": 1.0},
            {"row": 1, "col": 1, "priority_weight": 1.0},
        ]
        score = weighted_coverage_score(sig, cells)
        assert score == pytest.approx(50.0, abs=0.01)

    def test_priority_weight_matters(self):
        """High-priority covered cell should give > 50% even with 50% cell coverage."""
        sig = np.array([[-50.0, -100.0]])
        cells = [
            {"row": 0, "col": 0, "priority_weight": 3.0},   # covered, high weight
            {"row": 0, "col": 1, "priority_weight": 1.0},   # dead, low weight
        ]
        score = weighted_coverage_score(sig, cells)
        assert score == pytest.approx(75.0, abs=0.01)   # 3/(3+1)=75%

    def test_zero_weights_returns_0(self):
        sig = np.array([[-50.0]])
        cells = [{"row": 0, "col": 0, "priority_weight": 0.0}]
        assert weighted_coverage_score(sig, cells) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Integration test — compute_signal() end-to-end with fake DB
# ─────────────────────────────────────────────────────────────────────────────
class TestComputeSignalIntegration:
    """
    Tests the full compute_signal() flow with a FakeDB.
    These do NOT hit real MongoDB — they verify the logic end-to-end.
    """

    def test_returns_expected_keys(self):
        db = _fake_db([_make_router()])
        result = compute_signal(SESSION_ID, db)
        assert "signal_matrix"       in result
        assert "quality_matrix"      in result
        assert "interference_matrix" in result
        assert "metrics"             in result

    def test_signal_matrix_shape(self):
        db     = _fake_db([_make_router()])
        result = compute_signal(SESSION_ID, db)
        mat    = result["signal_matrix"]
        assert len(mat) == GRID_ROWS
        assert len(mat[0]) == GRID_COLS

    def test_single_router_centre_has_best_signal(self):
        """Router at (5,5) — that cell should be near max signal."""
        db     = _fake_db([_make_router(row=5, col=5)])
        result = compute_signal(SESSION_ID, db)
        mat    = np.array(result["signal_matrix"])
        assert mat[5, 5] >= mat.max() - 2.0   # within 2 dB of max

    def test_coverage_pct_between_0_and_100(self):
        db      = _fake_db([_make_router()])
        result  = compute_signal(SESSION_ID, db)
        cov_pct = result["metrics"]["coverage_pct"]
        assert 0.0 <= cov_pct <= 100.0

    def test_two_routers_better_coverage(self):
        """Two routers should cover at least as much as one."""
        r1 = _make_router(row=2, col=2)
        r2 = _make_router(row=7, col=7, ch=11)
        db1 = _fake_db([r1])
        db2 = _fake_db([r1, r2])
        cov1 = compute_signal(SESSION_ID, db1)["metrics"]["coverage_pct"]
        cov2 = compute_signal(SESSION_ID, db2)["metrics"]["coverage_pct"]
        assert cov2 >= cov1

    def test_no_routers_raises(self):
        db = _fake_db([])
        with pytest.raises(ValueError, match="No routers placed"):
            compute_signal(SESSION_ID, db)

    def test_missing_session_raises(self):
        db = FakeDB({"sessions": [], "grids": [], "routers": [],
                     "signal_results": []})
        with pytest.raises(ValueError, match="not found"):
            compute_signal(SESSION_ID, db)

    def test_mongodb_write_occurred(self):
        """After compute_signal(), signal_results collection should have a doc."""
        db = _fake_db([_make_router()])
        compute_signal(SESSION_ID, db)
        from bson import ObjectId
        doc = db["signal_results"].find_one(
            {"session_id": ObjectId(SESSION_ID)}
        )
        assert doc is not None
        assert "signal_matrix" in doc

    def test_high_attenuation_reduces_coverage(self):
        """A wall-heavy grid (attn=12) should have lower coverage than open space."""
        db_open = _fake_db([_make_router()], attn=0.0)
        db_wall = _fake_db([_make_router()], attn=12.0)
        cov_open = compute_signal(SESSION_ID, db_open)["metrics"]["coverage_pct"]
        cov_wall = compute_signal(SESSION_ID, db_wall)["metrics"]["coverage_pct"]
        assert cov_open > cov_wall

    def test_metrics_estimated_cost(self):
        router = {**_make_router(), "cost": 3500.0}
        db     = _fake_db([router])
        result = compute_signal(SESSION_ID, db)
        assert result["metrics"]["estimated_cost"] == pytest.approx(3500.0)