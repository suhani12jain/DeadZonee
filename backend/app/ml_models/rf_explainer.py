import json
import os
from collections import Counter
from math import sqrt

import anthropic
from dotenv import load_dotenv

from app.ml_models.placement_suggester import _pick_channel

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env"))

ANTHROPIC_KEY = os.getenv("ANTHROPIC_KEY", "")
DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _cell_lookup(cells):
    return {(int(cell["row"]), int(cell["col"])): cell for cell in cells}


def _cluster_cells(cluster):
    return [
        (int(cell["row"]), int(cell["col"]))
        for cell in cluster.get("cells", [])
    ]


def _safe_signal(signal_matrix, row, col, default=-200.0):
    try:
        return float(signal_matrix[row][col])
    except Exception:
        return default


def _safe_interference(interference_matrix, row, col, default=0.0):
    try:
        return float(interference_matrix[row][col])
    except Exception:
        return default


def _safe_quality(quality_matrix, row, col, default="DEAD"):
    try:
        return str(quality_matrix[row][col])
    except Exception:
        return default


def _nearest_routers(existing_routers, row, col, cell_size_m, limit=3):
    ranked = []
    for router in existing_routers:
        dr = (float(router.get("row", 0)) - row) * cell_size_m
        dc = (float(router.get("col", 0)) - col) * cell_size_m
        dist = sqrt(dr ** 2 + dc ** 2)
        ranked.append({
            "name": router.get("name", "AP"),
            "row": int(router.get("row", 0)),
            "col": int(router.get("col", 0)),
            "channel": int(router.get("channel", 1)),
            "frequency_mhz": float(router.get("frequency_mhz", 2400.0)),
            "distance_m": round(dist, 1),
        })
    ranked.sort(key=lambda item: item["distance_m"])
    return ranked[:limit]


def _cluster_stats(cluster, cell_map, signal_matrix, quality_matrix, interference_matrix, routers, cell_size_m):
    cells = _cluster_cells(cluster)
    if not cells:
        centroid_row = float(cluster.get("centroid_row", 0))
        centroid_col = float(cluster.get("centroid_col", 0))
        cells = [(int(round(centroid_row)), int(round(centroid_col)))]

    signals = [_safe_signal(signal_matrix, row, col) for row, col in cells]
    interference = [_safe_interference(interference_matrix, row, col) for row, col in cells]
    qualities = [_safe_quality(quality_matrix, row, col) for row, col in cells]
    zone_counter = Counter(
        cell_map.get((row, col), {}).get("zone_type", "unknown")
        for row, col in cells
    )
    attenuation_values = [
        float(cell_map.get((row, col), {}).get("attenuation", 0.0))
        for row, col in cells
    ]
    centroid_row = float(cluster.get("centroid_row", 0))
    centroid_col = float(cluster.get("centroid_col", 0))
    nearest = _nearest_routers(routers, centroid_row, centroid_col, cell_size_m)

    return {
        "avg_signal": round(sum(signals) / len(signals), 1) if signals else -200.0,
        "worst_signal": round(min(signals), 1) if signals else -200.0,
        "avg_interference": round(sum(interference) / len(interference), 3) if interference else 0.0,
        "quality_counts": dict(Counter(qualities)),
        "dominant_zone": zone_counter.most_common(1)[0][0] if zone_counter else "unknown",
        "zone_mix": dict(zone_counter),
        "avg_attenuation": round(sum(attenuation_values) / len(attenuation_values), 1) if attenuation_values else 0.0,
        "nearest_routers": nearest,
        "cells": cells,
    }


def _severity(cluster_size, worst_signal, avg_interference):
    if cluster_size >= 12 or worst_signal <= -92 or avg_interference >= 0.55:
        return "critical"
    if cluster_size >= 6 or worst_signal <= -88 or avg_interference >= 0.3:
        return "high"
    return "moderate"


def _cause_fragments(stats):
    causes = []
    nearest = stats["nearest_routers"][0] if stats["nearest_routers"] else None

    if nearest and nearest["distance_m"] >= 18:
        causes.append(f"the nearest AP is about {nearest['distance_m']:.0f} m away")

    if stats["avg_attenuation"] >= 8:
        causes.append(f"{stats['dominant_zone'].replace('_', ' ')} attenuation averages {stats['avg_attenuation']:.1f} dB")

    if stats["avg_interference"] >= 0.3:
        causes.append(f"co-channel overlap is elevated ({stats['avg_interference']:.2f})")

    if stats["worst_signal"] <= -90:
        causes.append(f"worst-case RSSI drops to {stats['worst_signal']:.1f} dBm")

    if not causes:
        causes.append(f"edge-of-cell coverage in the {stats['dominant_zone'].replace('_', ' ')} area is weak")

    return causes[:2]


def _recommended_channel(stats, routers, centroid_row, centroid_col, cell_size_m):
    if not routers:
        return None

    primary_router = stats["nearest_routers"][0] if stats["nearest_routers"] else None
    frequency_mhz = primary_router["frequency_mhz"] if primary_router else 2400.0
    channel = _pick_channel(
        routers,
        frequency_mhz,
        int(round(centroid_row)),
        int(round(centroid_col)),
        cell_size_m,
        range_m=50,
    )

    if primary_router and channel == primary_router["channel"] and stats["avg_interference"] < 0.3:
        return None

    return {
        "channel": int(channel),
        "frequency_mhz": float(frequency_mhz),
        "text": f"Try channel {int(channel)} on the nearest {int(frequency_mhz)} MHz AP before adding hardware."
    }


def _fallback_narrative(cluster, stats, routers, cell_size_m):
    centroid_row = float(cluster.get("centroid_row", 0))
    centroid_col = float(cluster.get("centroid_col", 0))
    cause_bits = _cause_fragments(stats)
    severity = _severity(int(cluster.get("size", 0)), stats["worst_signal"], stats["avg_interference"])
    quality_counts = stats["quality_counts"]
    dead_cells = int(quality_counts.get("DEAD", 0))
    poor_cells = int(quality_counts.get("POOR", 0))
    channel_tip = _recommended_channel(stats, routers, centroid_row, centroid_col, cell_size_m)

    explanation = (
        f"Cluster {cluster.get('cluster_id')} around row {centroid_row:.1f}, col {centroid_col:.1f} is weakest in the "
        f"{stats['dominant_zone'].replace('_', ' ')} region because {cause_bits[0]}"
    )
    if len(cause_bits) > 1:
        explanation += f" and {cause_bits[1]}"
    explanation += (
        f". {dead_cells} cells are fully dead and {poor_cells} are only poor, so traffic through this corridor will be unstable."
    )

    action = (
        channel_tip["text"]
        if channel_tip
        else "If this path carries users continuously, place an additional AP near the cluster centroid."
    )

    title = f"{stats['dominant_zone'].replace('_', ' ').title()} cluster {cluster.get('cluster_id')}"
    headline = f"{title} is {severity} due to low RSSI and local RF conditions."

    return {
        "cluster_id": int(cluster.get("cluster_id", 0)),
        "title": title,
        "headline": headline,
        "explanation": explanation,
        "action": action,
        "severity": severity,
        "size": int(cluster.get("size", 0)),
        "centroid_row": round(centroid_row, 2),
        "centroid_col": round(centroid_col, 2),
        "avg_signal": stats["avg_signal"],
        "worst_signal": stats["worst_signal"],
        "avg_interference": stats["avg_interference"],
        "dominant_zone": stats["dominant_zone"],
        "nearest_routers": stats["nearest_routers"],
        "recommended_channel": channel_tip,
    }


def _llm_context(metrics, routers, narratives):
    return {
        "coverage_pct": metrics.get("coverage_pct"),
        "avg_signal": metrics.get("avg_signal"),
        "interference_score": metrics.get("interference_score"),
        "router_count": len(routers),
        "narratives": [
            {
                "cluster_id": item["cluster_id"],
                "title": item["title"],
                "severity": item["severity"],
                "size": item["size"],
                "avg_signal": item["avg_signal"],
                "worst_signal": item["worst_signal"],
                "avg_interference": item["avg_interference"],
                "dominant_zone": item["dominant_zone"],
                "action": item["action"],
            }
            for item in narratives
        ],
    }


def _call_claude(metrics, routers, narratives, api_key):
    if not api_key or api_key.startswith("your_") or not narratives:
        return None

    prompt = (
        "You are an RF operations explainer for network installers. "
        "Return JSON with keys summary and narratives. summary must be one short paragraph. "
        "narratives must be an array with one item per cluster. Each item must contain cluster_id, headline, explanation, and action. "
        "Keep each explanation under 45 words and each action under 20 words. "
        "Do not invent numbers. Context: "
        f"{json.dumps(_llm_context(metrics, routers, narratives))}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=500,
            timeout=12,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(response.content[0].text)
        return payload
    except Exception as exc:
        print(f"[rf_explainer] Claude API failed ({exc}) — using fallback")
        return None


def build_rf_explanations(session_doc, grid_doc, signal_doc, deadzones_doc, routers, anthropic_key=None):
    if not signal_doc:
        raise ValueError("No signal results found. Run analysis first.")

    clusters = (deadzones_doc or {}).get("clusters", []) or []
    signal_matrix = signal_doc.get("signal_matrix", [])
    quality_matrix = signal_doc.get("quality_matrix", [])
    interference_matrix = signal_doc.get("interference_matrix", [])
    metrics = signal_doc.get("metrics", {})
    cell_size_m = float(session_doc.get("cell_size_m", 1.0))
    cell_map = _cell_lookup((grid_doc or {}).get("cells", []))

    narratives = []
    for cluster in clusters[:3]:
        stats = _cluster_stats(
            cluster,
            cell_map,
            signal_matrix,
            quality_matrix,
            interference_matrix,
            routers,
            cell_size_m,
        )
        narratives.append(_fallback_narrative(cluster, stats, routers, cell_size_m))

    if narratives:
        lead = narratives[0]
        summary = (
            f"Coverage is {metrics.get('coverage_pct', 0):.1f}% with {len(clusters)} weak cluster(s). "
            f"The main issue is {lead['title'].lower()}, where signal averages {lead['avg_signal']:.1f} dBm"
            f" and interference is {lead['avg_interference']:.2f}."
        )
    else:
        summary = (
            f"Coverage is {metrics.get('coverage_pct', 0):.1f}% and no dead-zone clusters remain large enough to explain."
        )

    source = "fallback"
    llm_payload = _call_claude(metrics, routers, narratives, anthropic_key or ANTHROPIC_KEY)
    if llm_payload:
        source = "anthropic"
        summary = str(llm_payload.get("summary") or summary)
        llm_narratives = {
            int(item.get("cluster_id", 0)): item
            for item in llm_payload.get("narratives", [])
            if isinstance(item, dict)
        }
        narratives = [
            {
                **item,
                "headline": str(llm_narratives.get(item["cluster_id"], {}).get("headline") or item["headline"]),
                "explanation": str(llm_narratives.get(item["cluster_id"], {}).get("explanation") or item["explanation"]),
                "action": str(llm_narratives.get(item["cluster_id"], {}).get("action") or item["action"]),
            }
            for item in narratives
        ]

    return {
        "summary": summary,
        "narratives": narratives,
        "source": source,
        "cluster_count": len(clusters),
        "router_count": len(routers),
    }
