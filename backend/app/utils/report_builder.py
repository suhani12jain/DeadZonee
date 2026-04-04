"""
utils/report_builder.py
-----------------------
Builds a multi-page PDF report using ReportLab.

Pages:
  1. Cover — project name, building, date, key metrics
  2. Router Table — all placed access points
  3. Signal Heatmap — colour-coded matplotlib grid image
  4. Dead Zone Summary — cluster list
  5. Optimisation Results — score before/after
  6. AI Suggestion — explanation text (if accepted)
"""

import io
import math
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from reportlab.lib.pagesizes  import A4
from reportlab.lib.units       import cm
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib             import colors
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)


# ── Colour palette ────────────────────────────────────────────────────────────
TEAL   = colors.HexColor("#0D9488")
NAVY   = colors.HexColor("#0F172A")
LIGHT  = colors.HexColor("#F0FDFA")
GRAY   = colors.HexColor("#64748B")
WHITE  = colors.white
BLACK  = colors.black
RED    = colors.HexColor("#EF4444")
GREEN  = colors.HexColor("#10B981")
YELLOW = colors.HexColor("#F59E0B")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title":    ParagraphStyle("title",   fontName="Helvetica-Bold",  fontSize=22, textColor=TEAL,  spaceAfter=6),
        "h2":       ParagraphStyle("h2",      fontName="Helvetica-Bold",  fontSize=14, textColor=NAVY,  spaceAfter=4),
        "h3":       ParagraphStyle("h3",      fontName="Helvetica-Bold",  fontSize=11, textColor=GRAY,  spaceAfter=4),
        "body":     ParagraphStyle("body",    fontName="Helvetica",        fontSize=10, textColor=BLACK, spaceAfter=4, leading=14),
        "small":    ParagraphStyle("small",   fontName="Helvetica",        fontSize=8,  textColor=GRAY),
        "code":     ParagraphStyle("code",    fontName="Courier",          fontSize=9,  textColor=TEAL),
        "caption":  ParagraphStyle("caption", fontName="Helvetica-Oblique",fontSize=8,  textColor=GRAY,  alignment=1),
    }


def _hdr_table(row_data, col_widths):
    """Single-row header table."""
    t = Table([row_data], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("TOPPADDING",  (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING",(0,0), (-1, 0), 6),
        ("LEFTPADDING", (0, 0), (-1, 0), 6),
        ("GRID",        (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    return t


def _data_table(header_row, data_rows, col_widths):
    """Full table with header row + data rows with alternating shading."""
    all_rows = [header_row] + data_rows
    t = Table(all_rows, colWidths=col_widths, repeatRows=1)
    style = [
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        # Body
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, _ in enumerate(data_rows):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i+1), (-1, i+1), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _signal_heatmap_image(signal_matrix, rows, cols):
    """Render the signal_matrix as a colour-coded matplotlib image; return BytesIO PNG."""
    if not signal_matrix or rows == 0 or cols == 0:
        return None

    mat = np.array(signal_matrix, dtype=float)

    # Map dBm to 0–1 quality score: -50 (best) → 1.0,  -100 (dead) → 0.0
    normalised = np.clip((mat + 100) / 50.0, 0.0, 1.0)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "signal",
        [(0.0, "#000000"),   # DEAD   < -85
         (0.3, "#EF4444"),   # POOR   -85 to -75
         (0.5, "#F97316"),   # FAIR   -75 to -67
         (0.7, "#F59E0B"),   # GOOD   -67 to -50
         (1.0, "#10B981")],  # EXCEL  > -50
    )

    fig, ax = plt.subplots(figsize=(min(cols * 0.4, 12), min(rows * 0.4, 8)))
    im = ax.imshow(normalised, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_title("Signal Strength Heatmap", fontsize=12, color="#0F172A")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.colorbar(im, ax=ax, label="Signal Quality (0=Dead, 1=Excellent)")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Main build function ───────────────────────────────────────────────────────

def build_pdf(data: dict) -> bytes:
    """
    Parameters
    ----------
    data : dict with keys:
        session, grid, routers, signal, deadzones,
        optimisation, suggestion

    Returns
    -------
    bytes — PDF binary
    """
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm,  bottomMargin=2*cm)
    S      = _styles()
    story  = []
    W      = A4[0] - 4*cm          # usable width

    session      = data.get("session")      or {}
    routers      = data.get("routers")      or []
    signal       = data.get("signal")       or {}
    deadzones    = data.get("deadzones")    or {}
    optimisation = data.get("optimisation") or {}
    suggestion   = data.get("suggestion")  or {}
    grid         = data.get("grid")        or {}

    grid_rows = session.get("grid_rows", 0)
    grid_cols = session.get("grid_cols", 0)
    metrics   = signal.get("metrics", {})
    clusters  = deadzones.get("clusters", [])

    # ── PAGE 1: Cover ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("DeadZero", S["title"]))
    story.append(Paragraph("Smart Wireless Infrastructure Report", S["h2"]))
    story.append(Spacer(1, 0.4*cm))

    meta_rows = [
        ["Project",    session.get("project_name",  "—")],
        ["Building",   session.get("building_name", "—")],
        ["Floor Size", f"{session.get('width_m','?')} m × {session.get('height_m','?')} m"],
        ["Cell Size",  f"{session.get('cell_size_m','?')} m"],
        ["Grid",       f"{grid_rows} rows × {grid_cols} cols = {grid_rows*grid_cols} cells"],
        ["Generated",  datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
    ]
    meta_t = Table(meta_rows, colWidths=[3.5*cm, W - 3.5*cm])
    meta_t.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1,-1), 10),
        ("TOPPADDING",(0, 0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("TEXTCOLOR", (0, 0), (0, -1), TEAL),
        ("GRID",      (0, 0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 0.8*cm))

    # Key metrics banner
    cov  = metrics.get("coverage_pct",       "—")
    avg  = metrics.get("avg_signal",          "—")
    dz   = deadzones.get("dead_zone_count",   "—")
    cost = metrics.get("estimated_cost",      "—")
    kpi_rows = [
        ["Coverage %", "Avg Signal", "Dead Cells", "Est. Cost"],
        [
            f"{cov:.1f}%" if isinstance(cov, (int,float)) else str(cov),
            f"{avg:.1f} dBm" if isinstance(avg,(int,float)) else str(avg),
            str(dz),
            f"₹{cost:,.0f}" if isinstance(cost,(int,float)) else str(cost),
        ]
    ]
    kpi_t = Table(kpi_rows, colWidths=[W/4]*4)
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), TEAL),
        ("TEXTCOLOR",     (0,0),(-1,0), WHITE),
        ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1),11),
        ("FONTNAME",      (0,1),(-1,1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1),(-1,1), NAVY),
        ("BACKGROUND",    (0,1),(-1,1), LIGHT),
        ("ALIGN",         (0,0),(-1,-1),"CENTER"),
        ("TOPPADDING",    (0,0),(-1,-1),8),
        ("BOTTOMPADDING", (0,0),(-1,-1),8),
        ("GRID",          (0,0),(-1,-1),0.5, colors.HexColor("#CBD5E1")),
    ]))
    story.append(kpi_t)
    story.append(PageBreak())

    # ── PAGE 2: Router Table ──────────────────────────────────────────────────
    story.append(Paragraph("Placed Access Points", S["h2"]))
    story.append(Spacer(1, 0.2*cm))
    if routers:
        col_w = [W*p for p in [0.15, 0.08, 0.08, 0.12, 0.12, 0.10, 0.10, 0.10, 0.15]]
        hdr   = ["Name", "Row", "Col", "Tx Power", "Freq (MHz)", "Channel", "Range (m)", "Cost (₹)", "AI Placed"]
        rows_data = [
            [
                r.get("name",""),
                str(r.get("row","")),
                str(r.get("col","")),
                f"{r.get('tx_power_dbm','')} dBm",
                str(r.get("frequency_mhz","")),
                str(r.get("channel","")),
                f"{r.get('range_m','')} m",
                f"₹{r.get('cost',0):,.0f}",
                "Yes" if r.get("is_suggested") else "No",
            ]
            for r in routers
        ]
        story.append(_data_table(hdr, rows_data, col_w))
    else:
        story.append(Paragraph("No routers placed.", S["body"]))
    story.append(PageBreak())

    # ── PAGE 3: Signal Heatmap ────────────────────────────────────────────────
    story.append(Paragraph("Signal Strength Heatmap", S["h2"]))
    story.append(Spacer(1, 0.2*cm))
    signal_matrix = signal.get("signal_matrix", [])
    if signal_matrix and grid_rows > 0 and grid_cols > 0:
        img_buf = _signal_heatmap_image(signal_matrix, grid_rows, grid_cols)
        if img_buf:
            img = Image(img_buf, width=W, height=min(W * grid_rows / max(grid_cols,1), 14*cm))
            story.append(img)
            story.append(Paragraph(
                "Green = Excellent (>-50 dBm)  |  Yellow = Good (-50 to -67)  |  "
                "Orange = Fair (-67 to -75)  |  Red = Poor (-75 to -85)  |  Black = Dead (<-85)",
                S["caption"]
            ))
    else:
        story.append(Paragraph("Signal matrix not available.", S["body"]))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Full Signal Metrics", S["h3"]))
    m_rows = [
        ["Metric",                   "Value"],
        ["Coverage %",               f"{metrics.get('coverage_pct','—'):.1f}%" if isinstance(metrics.get('coverage_pct'),float) else "—"],
        ["Average Signal",           f"{metrics.get('avg_signal','—'):.1f} dBm" if isinstance(metrics.get('avg_signal'),float) else "—"],
        ["Worst Signal",             f"{metrics.get('worst_signal','—'):.1f} dBm" if isinstance(metrics.get('worst_signal'),float) else "—"],
        ["Interference Score",       str(metrics.get("interference_score","—"))],
        ["Dead Zone Cell Count",     str(deadzones.get("dead_zone_count","—"))],
        ["Dead Zone Cluster Count",  str(len(clusters))],
        ["Router Count",             str(len(routers))],
        ["Estimated Cost",           f"₹{metrics.get('estimated_cost',0):,.0f}" if isinstance(metrics.get('estimated_cost'),(int,float)) else "—"],
    ]
    story.append(_data_table(m_rows[0], m_rows[1:], [W*0.5, W*0.5]))
    story.append(PageBreak())

    # ── PAGE 4: Dead Zone Clusters ────────────────────────────────────────────
    story.append(Paragraph("Dead Zone Cluster Analysis", S["h2"]))
    story.append(Spacer(1, 0.2*cm))
    if clusters:
        c_hdr  = ["Cluster ID", "Size (cells)", "Centroid Row", "Centroid Col"]
        c_rows = [
            [
                str(c.get("cluster_id",i+1)),
                str(c.get("size","")),
                f"{c.get('centroid_row',0):.1f}",
                f"{c.get('centroid_col',0):.1f}",
            ]
            for i, c in enumerate(clusters)
        ]
        story.append(_data_table(c_hdr, c_rows, [W*0.25]*4))
    else:
        story.append(Paragraph("No significant dead zone clusters detected.", S["body"]))
    story.append(PageBreak())

    # ── PAGE 5: Optimisation Results ──────────────────────────────────────────
    story.append(Paragraph("Optimisation Results", S["h2"]))
    story.append(Spacer(1, 0.2*cm))
    if optimisation:
        o_rows = [
            ["Algorithm",         optimisation.get("algorithm","—")],
            ["Original Score",    f"{optimisation.get('original_score',0):.3f}"],
            ["Optimised Score",   f"{optimisation.get('optimised_score',0):.3f}"],
            ["Improvement",       f"{optimisation.get('improvement_pct',0):.1f}%"],
        ]
        story.append(_data_table(o_rows[0], o_rows[1:], [W*0.4, W*0.6]))
        story.append(Spacer(1, 0.4*cm))

        opt_routers = optimisation.get("optimised_routers", [])
        if opt_routers:
            story.append(Paragraph("Optimised Router Positions", S["h3"]))
            or_hdr  = ["Router ID", "New Row", "New Col"]
            or_rows = [
                [r.get("router_id","")[:12], str(r.get("new_row","")), str(r.get("new_col",""))]
                for r in opt_routers
            ]
            story.append(_data_table(or_hdr, or_rows, [W*0.5, W*0.25, W*0.25]))
    else:
        story.append(Paragraph("Optimisation has not been run for this session.", S["body"]))
    story.append(PageBreak())

    # ── PAGE 6: AI Suggestion ─────────────────────────────────────────────────
    story.append(Paragraph("AI Router Placement Suggestion", S["h2"]))
    story.append(Spacer(1, 0.2*cm))
    if suggestion:
        cfg = suggestion.get("suggested_config", {})
        s_rows = [
            ["Suggested Row",       str(suggestion.get("suggested_row","—"))],
            ["Suggested Col",       str(suggestion.get("suggested_col","—"))],
            ["Tx Power",            f"{cfg.get('tx_power','—')} dBm"],
            ["Frequency",           f"{cfg.get('frequency','—')} MHz"],
            ["Channel",             str(cfg.get("channel","—"))],
            ["Range",               f"{cfg.get('range','—')} m"],
            ["Expected Coverage Gain", f"{suggestion.get('coverage_gain_pct',0):.1f}%"],
            ["Accepted",            "Yes" if suggestion.get("accepted") else "No"],
        ]
        story.append(_data_table(s_rows[0], s_rows[1:], [W*0.4, W*0.6]))
        story.append(Spacer(1, 0.4*cm))
        expl = suggestion.get("explanation", "")
        if expl:
            story.append(Paragraph("AI Explanation", S["h3"]))
            story.append(Paragraph(expl, S["body"]))
    else:
        story.append(Paragraph("No AI suggestion has been generated for this session.", S["body"]))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)
    return buf.read()
