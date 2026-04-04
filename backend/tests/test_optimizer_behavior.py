import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml_models.optimizer import _build_allowed_cells, _snap_to_allowed


def test_snap_to_allowed_picks_nearest_valid_cell():
    allowed = [{"row": 0, "col": 0}, {"row": 4, "col": 4}, {"row": 2, "col": 3}]
    assert _snap_to_allowed(2, 2, allowed) == {"row": 2, "col": 3}


def test_build_allowed_cells_filters_disallowed_positions():
    cells = [
        {"row": 0, "col": 0, "allow_router": False},
        {"row": 0, "col": 1, "allow_router": True},
        {"row": 1, "col": 1, "allow_router": True},
    ]
    allowed = _build_allowed_cells(cells)
    assert {"row": 0, "col": 0} not in allowed
    assert {"row": 0, "col": 1} in allowed
