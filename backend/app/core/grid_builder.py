"""
grid_builder.py
---------------
Converts floor dimensions (metres) into an NxM cell grid.
Each cell stores its real-world position and default zone_type = 'no_zone'.

Called by: backend/app/routers/grid.py  →  POST /api/grid/create
"""


def build_grid(width_m: float, height_m: float, cell_size_m: float) -> dict:
    """
    Parameters
    ----------
    width_m     : floor width in metres
    height_m    : floor height in metres
    cell_size_m : size of each square cell in metres (e.g. 2.0)

    Returns
    -------
    {
        'grid_rows' : int,
        'grid_cols' : int,
        'cells'     : list[dict]   # one dict per cell
    }
    """
    rows = int(height_m / cell_size_m)
    cols = int(width_m  / cell_size_m)

    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append({
                "row":            r,
                "col":            c,
                "x_m":            round(c * cell_size_m, 4),   # left edge x in metres
                "y_m":            round(r * cell_size_m, 4),   # top  edge y in metres
                "zone_type":      "no_zone",
                "attenuation":    99.0,
                "priority_weight": 0.0,
                "allow_router":   False,
            })

    return {
        "grid_rows": rows,
        "grid_cols": cols,
        "cells":     cells,
    }
