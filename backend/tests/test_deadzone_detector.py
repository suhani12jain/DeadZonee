"""
tests/test_deadzone_detector.py  —  Member 1
DeadZero v3.0

Run:  python -m pytest tests/test_deadzone_detector.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np

from app.ml_models.deadzone_detector import (
    detect_deadzones,
    _build_clusters,
    MIN_CLUSTER_SIZE,
    DEAD_THRESHOLD_DBM,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fake DB (same pattern as test_signal_engine)
# ─────────────────────────────────────────────────────────────────────────────
class FakeCollection:
    def __init__(self, docs=None):
        self._docs = docs or []

    def find_one(self, query):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def replace_one(self, query, replacement, upsert=False):
        for i, doc in enumerate(self._docs):
            if all(doc.get(k) == v for k, v in query.items()):
                self._docs[i] = replacement
                return
        if upsert:
            self._docs.append(replacement)


class FakeDB:
    def __init__(self, signal_matrix: np.ndarray):
        from bson import ObjectId
        sid = ObjectId(SESSION_ID)
        self._colls = {
            "signal_results": FakeCollection([{
                "session_id": sid,
                "signal_matrix": signal_matrix.tolist(),
            }]),
            "deadzones": FakeCollection([]),
        }

    def __getitem__(self, name):
        if name not in self._colls:
            self._colls[name] = FakeCollection()
        return self._colls[name]


SESSION_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"   # 24-char fake ObjectId


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _make_signal_matrix(rows=10, cols=10, dead_region=None,
                         good_value=-50.0, dead_value=-95.0):
    """
    Creates a uniform 'good' signal matrix, then optionally stamps
    a rectangle of dead cells.

    dead_region: (r_start, r_end, c_start, c_end)
    """
    mat = np.full((rows, cols), good_value, dtype=np.float64)
    if dead_region:
        r0, r1, c0, c1 = dead_region
        mat[r0:r1, c0:c1] = dead_value
    return mat


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — _build_clusters()
# ─────────────────────────────────────────────────────────────────────────────
class TestBuildClusters:
    def test_single_large_cluster(self):
        from scipy import ndimage
        dead_mask = np.zeros((10, 10), dtype=bool)
        dead_mask[3:7, 3:7] = True   # 4x4 = 16 cells
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        assert len(clusters) == 1
        assert clusters[0]["size"] == 16

    def test_two_separate_clusters(self):
        from scipy import ndimage
        dead_mask = np.zeros((10, 10), dtype=bool)
        dead_mask[0:3, 0:3] = True   # 9 cells
        dead_mask[7:10, 7:10] = True # 9 cells
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        assert len(clusters) == 2
        assert all(c["size"] == 9 for c in clusters)

    def test_noise_cluster_filtered(self):
        """Cluster of size <= MIN_CLUSTER_SIZE must be removed."""
        from scipy import ndimage
        dead_mask = np.zeros((10, 10), dtype=bool)
        # Tiny 1-cell cluster
        dead_mask[0, 0] = True
        # Large cluster
        dead_mask[5:9, 5:9] = True
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        sizes = [c["size"] for c in clusters]
        assert all(s > MIN_CLUSTER_SIZE for s in sizes)

    def test_clusters_sorted_by_size_descending(self):
        from scipy import ndimage
        dead_mask = np.zeros((20, 20), dtype=bool)
        dead_mask[0:5, 0:5] = True    # 25 cells
        dead_mask[10:12, 10:12] = True # 4 cells
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        sizes = [c["size"] for c in clusters]
        assert sizes == sorted(sizes, reverse=True)

    def test_centroid_in_expected_range(self):
        from scipy import ndimage
        dead_mask = np.zeros((10, 10), dtype=bool)
        dead_mask[4:6, 4:6] = True   # 2x2 = 4 cells, centroid ~(4.5, 4.5)
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        assert len(clusters) == 1
        c = clusters[0]
        assert 4.0 <= c["centroid_row"] <= 5.0
        assert 4.0 <= c["centroid_col"] <= 5.0

    def test_cells_list_populated(self):
        from scipy import ndimage
        dead_mask = np.zeros((5, 5), dtype=bool)
        dead_mask[1:4, 1:4] = True   # 9 cells (3x3)
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        assert len(clusters) == 1
        # Should have 9 cell entries
        assert len(clusters[0]["cells"]) == 9
        # Each cell entry must have row and col
        for cell in clusters[0]["cells"]:
            assert "row" in cell and "col" in cell

    def test_cluster_ids_sequential(self):
        from scipy import ndimage
        dead_mask = np.zeros((20, 20), dtype=bool)
        dead_mask[0:4, 0:4] = True
        dead_mask[10:14, 10:14] = True
        labeled, num = ndimage.label(dead_mask)
        clusters = _build_clusters(dead_mask, labeled, num)
        ids = [c["cluster_id"] for c in clusters]
        assert ids == list(range(1, len(clusters) + 1))


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — detect_deadzones() with FakeDB
# ─────────────────────────────────────────────────────────────────────────────
class TestDetectDeadzonesIntegration:

    def test_no_dead_zones_returns_empty(self):
        """All cells well above threshold → no clusters."""
        mat = _make_signal_matrix(dead_region=None)
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        assert result["dead_zone_count"] == 0
        assert result["clusters"] == []

    def test_one_dead_region_detected(self):
        mat = _make_signal_matrix(dead_region=(2, 6, 2, 6))  # 4x4 = 16 dead
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        assert result["dead_zone_count"] == 16
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["size"] == 16

    def test_dead_zone_mask_shape(self):
        mat = _make_signal_matrix(rows=8, cols=12, dead_region=(0, 4, 0, 6))
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        mask = result["dead_zone_mask"]
        assert len(mask) == 8
        assert len(mask[0]) == 12

    def test_dead_zone_mask_values_are_bool(self):
        mat = _make_signal_matrix(dead_region=(0, 3, 0, 3))
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        for row in result["dead_zone_mask"]:
            for val in row:
                assert isinstance(val, bool)

    def test_two_separate_dead_zones(self):
        mat = np.full((10, 20), -50.0)
        mat[1:5, 1:5]   = -95.0   # cluster 1 (16 cells)
        mat[6:9, 12:16] = -95.0   # cluster 2 (12 cells)
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        assert len(result["clusters"]) == 2
        assert result["dead_zone_count"] == 28

    def test_noise_clusters_removed(self):
        """Single dead cell shouldn't appear as a cluster."""
        mat = _make_signal_matrix()
        mat[0, 0] = -95.0   # noise — 1 cell only
        mat[5:8, 5:8] = -95.0  # real cluster (9 cells)
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        # noise cluster filtered, only 1 real cluster
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["size"] == 9

    def test_dead_zone_count_matches_mask(self):
        mat = _make_signal_matrix(dead_region=(3, 7, 3, 7))  # 4x4=16
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        mask_true = sum(val for row in result["dead_zone_mask"] for val in row)
        assert mask_true == result["dead_zone_count"]

    def test_mongodb_write_occurred(self):
        from bson import ObjectId
        mat = _make_signal_matrix(dead_region=(1, 5, 1, 5))
        db  = FakeDB(mat)
        detect_deadzones(SESSION_ID, db)
        doc = db["deadzones"].find_one(
            {"session_id": ObjectId(SESSION_ID)}
        )
        assert doc is not None
        assert "dead_zone_mask"  in doc
        assert "dead_zone_count" in doc
        assert "clusters"        in doc

    def test_missing_signal_results_raises(self):
        """detect_deadzones must raise if no signal_results for session."""
        from bson import ObjectId
        db = FakeDB.__new__(FakeDB)
        db._colls = {
            "signal_results": FakeCollection([]),  # empty — no doc
            "deadzones": FakeCollection([]),
        }
        with pytest.raises(ValueError, match="No signal results"):
            detect_deadzones(SESSION_ID, db)

    def test_fully_dead_grid(self):
        """If entire grid is dead, dead_zone_count == rows*cols."""
        rows, cols = 5, 5
        mat = np.full((rows, cols), -95.0)
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        assert result["dead_zone_count"] == rows * cols

    def test_centroid_within_grid_bounds(self):
        """Cluster centroid rows/cols must be within grid dimensions."""
        mat = _make_signal_matrix(rows=10, cols=10,
                                   dead_region=(3, 7, 3, 7))
        db  = FakeDB(mat)
        result = detect_deadzones(SESSION_ID, db)
        for cluster in result["clusters"]:
            assert 0 <= cluster["centroid_row"] < 10
            assert 0 <= cluster["centroid_col"] < 10