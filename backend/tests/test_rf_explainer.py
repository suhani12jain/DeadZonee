import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml_models.rf_explainer import build_rf_explanations


def test_build_rf_explanations_returns_cluster_narratives():
    session_doc = {"session_id": "sess1", "cell_size_m": 2.0}
    grid_doc = {
        "cells": [
            {"row": r, "col": c, "zone_type": "corridor", "attenuation": 10.0}
            for r in range(4)
            for c in range(4)
        ]
    }
    signal_doc = {
        "signal_matrix": [
            [-92.0, -90.0, -88.0, -70.0],
            [-93.0, -91.0, -89.0, -72.0],
            [-86.0, -85.5, -84.0, -68.0],
            [-70.0, -69.0, -67.0, -65.0],
        ],
        "quality_matrix": [
            ["DEAD", "DEAD", "POOR", "GOOD"],
            ["DEAD", "DEAD", "POOR", "GOOD"],
            ["DEAD", "DEAD", "POOR", "GOOD"],
            ["GOOD", "GOOD", "GOOD", "EXCELLENT"],
        ],
        "interference_matrix": [
            [0.7, 0.6, 0.4, 0.0],
            [0.7, 0.5, 0.3, 0.0],
            [0.4, 0.2, 0.1, 0.0],
            [0.0, 0.0, 0.0, 0.0],
        ],
        "metrics": {"coverage_pct": 62.5, "avg_signal": -79.1, "interference_score": 0.24},
    }
    deadzones_doc = {
        "clusters": [
            {
                "cluster_id": 1,
                "size": 6,
                "centroid_row": 1.0,
                "centroid_col": 1.0,
                "cells": [
                    {"row": 0, "col": 0},
                    {"row": 0, "col": 1},
                    {"row": 1, "col": 0},
                    {"row": 1, "col": 1},
                    {"row": 2, "col": 0},
                    {"row": 2, "col": 1},
                ],
            }
        ]
    }
    routers = [
        {"name": "AP-01", "row": 0, "col": 3, "channel": 1, "frequency_mhz": 2400.0},
        {"name": "AP-02", "row": 3, "col": 3, "channel": 1, "frequency_mhz": 2400.0},
    ]

    result = build_rf_explanations(
        session_doc,
        grid_doc,
        signal_doc,
        deadzones_doc,
        routers,
        anthropic_key="",
    )

    assert result["source"] == "fallback"
    assert "Coverage is 62.5%" in result["summary"]
    assert len(result["narratives"]) == 1

    narrative = result["narratives"][0]
    assert narrative["cluster_id"] == 1
    assert narrative["dominant_zone"] == "corridor"
    assert narrative["severity"] in {"high", "critical"}
    assert "corridor" in narrative["explanation"].lower()
    assert narrative["recommended_channel"]["channel"] in {6, 11}


def test_build_rf_explanations_handles_clean_results():
    result = build_rf_explanations(
        {"session_id": "sess1", "cell_size_m": 2.0},
        {"cells": []},
        {
            "signal_matrix": [[-60.0]],
            "quality_matrix": [["GOOD"]],
            "interference_matrix": [[0.0]],
            "metrics": {"coverage_pct": 100.0, "avg_signal": -60.0, "interference_score": 0.0},
        },
        {"clusters": []},
        [],
        anthropic_key="",
    )

    assert result["narratives"] == []
    assert "no dead-zone clusters remain" in result["summary"].lower()
