import React, { useState } from 'react'
import useStore from '../../store/useStore'
import { getZone, signalLabel } from '../../constants/zoneConfig'

const OVERLAY_META = {
  heatmap: {
    title: 'Signal Heat Explanation',
    accent: 'var(--sig-good)',
    intro: 'This view explains raw RSSI strength cell by cell.',
    legend: [
      { color: '#10B981', label: 'Excellent', meaning: 'Above -50 dBm, strong client performance.' },
      { color: '#F59E0B', label: 'Good', meaning: 'Between -50 and -67 dBm, usable for most traffic.' },
      { color: '#F97316', label: 'Fair', meaning: 'Between -67 and -75 dBm, service is weaker.' },
      { color: '#EF4444', label: 'Poor', meaning: 'Between -75 and -85 dBm, likely unstable.' },
      { color: '#000000', label: 'Dead', meaning: 'Below -85 dBm, service is effectively gone.' },
    ],
  },
  interference: {
    title: 'Interference Explanation',
    accent: '#a855f7',
    intro: 'This view explains where overlapping channels are likely to reduce throughput.',
    legend: [
      { color: '#d8b4fe', label: 'Low', meaning: 'Some overlap exists, but it is unlikely to dominate throughput.' },
      { color: '#a855f7', label: 'Elevated', meaning: 'Nearby APs are competing in the same space.' },
      { color: '#6b21a8', label: 'Severe', meaning: 'Channel reuse is likely hurting client performance.' },
    ],
  },
  deadzone: {
    title: 'Dead Zone Explanation',
    accent: 'var(--danger)',
    intro: 'This view isolates cells that have fallen below the usable coverage threshold.',
    legend: [
      { color: '#000000', label: 'Dead', meaning: 'The cell is below the dead-zone threshold.' },
      { color: '#ff4d6d', label: 'Cross Mark', meaning: 'Marked as a critical no-service cell.' },
    ],
  },
  priority: {
    title: 'Priority Weight Explanation',
    accent: '#f59e0b',
    intro: 'This view explains where weak coverage hurts the weighted score most.',
    legend: [
      { color: '#fde68a', label: 'Low Weight', meaning: 'Coverage matters here, but it is not a top target.' },
      { color: '#f59e0b', label: 'High Weight', meaning: 'Coverage loss here has higher planning impact.' },
    ],
  },
}

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0
}

function buildOverlaySummary(state) {
  const {
    focusedOverlay,
    overlays,
    signalMatrix,
    interferenceMatrix,
    deadZoneMask,
    cells,
    metrics,
    rfExplanations,
  } = state

  if (!overlays[focusedOverlay]) return null

  if (focusedOverlay === 'heatmap' && signalMatrix?.length) {
    const flat = signalMatrix.flat().filter(v => typeof v === 'number' && v > -200)
    const mean = average(flat)
    return {
      stats: [
        `Average signal is ${mean.toFixed(1)} dBm, which rates as ${signalLabel(mean)}.`,
        `${flat.filter(v => v <= -75).length} cells are weak at or below -75 dBm.`,
        `${flat.filter(v => v <= -85).length} cells are effectively dead at or below -85 dBm.`,
      ],
      explanation: rfExplanations?.summary || 'Use this layer to find corridors and room edges where the signal decays before clients fully disconnect.',
    }
  }

  if (focusedOverlay === 'interference' && interferenceMatrix?.length) {
    const flat = interferenceMatrix.flat().filter(v => typeof v === 'number')
    const lead = rfExplanations?.narratives?.find(item => item.avg_interference >= 0.3)
    return {
      stats: [
        `Average overlap score is ${average(flat).toFixed(2)} across the grid.`,
        `${flat.filter(v => v >= 0.5).length} cells show elevated overlap.`,
        `${flat.filter(v => v >= 0.8).length} cells are severe enough to justify channel changes first.`,
      ],
      explanation: lead?.action || 'Purple areas mean nearby routers are strong on overlapping channels, so clients hear too many contenders in the same space.',
    }
  }

  if (focusedOverlay === 'deadzone' && deadZoneMask?.length) {
    const dead = deadZoneMask.flat().filter(Boolean).length
    const lead = rfExplanations?.narratives?.[0]
    return {
      stats: [
        `${dead} cells are below the dead-zone threshold.`,
        `${rfExplanations?.cluster_count ?? 0} cluster(s) are large enough to matter operationally.`,
        lead ? `The main weak region centers on row ${lead.centroid_row}, col ${lead.centroid_col}.` : 'No major weak cluster is currently dominant.',
      ],
      explanation: lead?.explanation || 'Use this layer when you need the clearest view of where service is not recoverable without a placement or channel change.',
    }
  }

  if (focusedOverlay === 'priority' && cells?.length) {
    const weighted = cells.filter(cell => (cell.priority_weight ?? 0) >= 1.0)
    const topZones = [...new Set(weighted.map(cell => getZone(cell.zone_type).label))].slice(0, 3)
    return {
      stats: [
        `${weighted.length} cells are marked as high-impact coverage targets.`,
        `Coverage is currently ${metrics?.coverage_pct?.toFixed?.(1) ?? '—'}%.`,
        topZones.length ? `Top weighted areas: ${topZones.join(', ')}.` : 'No high-priority zones are painted yet.',
      ],
      explanation: 'Amber cells should drive optimisation first because the scorer values those zones more heavily than low-priority space.',
    }
  }

  return null
}

function buildTopicChips(focusedOverlay, leadNarrative) {
  const base = {
    heatmap: ['Coverage', 'Weak Cells', 'Dead Spots'],
    interference: ['Channel Clash', 'Overlap Cells', 'Next Action'],
    deadzone: ['Dead Clusters', 'Main Weak Region', 'Recovery Plan'],
    priority: ['High Impact', 'Top Zones', 'Optimisation Goal'],
  }[focusedOverlay] ?? []

  if (leadNarrative?.recommended_channel?.channel) {
    return [...base, `Try ch ${leadNarrative.recommended_channel.channel}`]
  }
  return base
}

function buildHoveredInsight(state) {
  const {
    hoveredCell,
    cells,
    signalMatrix,
    qualityMatrix,
    interferenceMatrix,
    deadZoneMask,
    focusedOverlay,
  } = state

  if (!hoveredCell) return null

  const { row, col } = hoveredCell
  const cell = cells.find(item => item.row === row && item.col === col)
  const zoneLabel = cell ? getZone(cell.zone_type).label : 'Unknown'
  const signal = signalMatrix?.[row]?.[col]
  const quality = qualityMatrix?.[row]?.[col] || (signal != null ? signalLabel(signal) : '—')
  const interference = interferenceMatrix?.[row]?.[col]
  const isDead = !!deadZoneMask?.[row]?.[col]

  if (focusedOverlay === 'heatmap') {
    return {
      title: `Hovered cell: row ${row}, col ${col}`,
      lines: [
        `Zone: ${zoneLabel}`,
        signal != null ? `Signal: ${signal.toFixed(1)} dBm (${quality})` : 'Signal not available yet.',
        isDead ? 'This cell is already below the dead-zone threshold.' : 'This cell is still above the dead-zone threshold.',
      ],
    }
  }

  if (focusedOverlay === 'interference') {
    return {
      title: `Hovered cell: row ${row}, col ${col}`,
      lines: [
        `Zone: ${zoneLabel}`,
        interference != null ? `Overlap score: ${interference.toFixed(2)}` : 'Interference not available yet.',
        interference >= 0.5
          ? 'This cell is a strong candidate for a channel change.'
          : 'This cell is not currently a high-overlap hotspot.',
      ],
    }
  }

  if (focusedOverlay === 'deadzone') {
    return {
      title: `Hovered cell: row ${row}, col ${col}`,
      lines: [
        `Zone: ${zoneLabel}`,
        isDead ? 'This cell is in the dead-zone mask.' : 'This cell is outside the dead-zone mask.',
        signal != null ? `Measured signal here: ${signal.toFixed(1)} dBm.` : 'Signal not available yet.',
      ],
    }
  }

  if (focusedOverlay === 'priority') {
    return {
      title: `Hovered cell: row ${row}, col ${col}`,
      lines: [
        `Zone: ${zoneLabel}`,
        `Priority weight: ${cell?.priority_weight ?? '—'}`,
        cell?.allow_router ? 'Router placement is allowed here.' : 'Router placement is blocked here.',
      ],
    }
  }

  return null
}

function buildQuestions(focusedOverlay, leadNarrative) {
  const base = {
    heatmap: [
      {
        q: 'Why is this area red or black?',
        a: 'Red and black cells mean signal has fallen into poor or dead ranges. That usually points to too much distance from the nearest AP, too much attenuation through rooms, or both.',
      },
      {
        q: 'What should I change first?',
        a: leadNarrative?.action || 'Start by checking whether the weak region needs a closer AP or whether a placement move could pull stronger coverage into that area.',
      },
    ],
    interference: [
      {
        q: 'Why are these cells purple?',
        a: 'Purple cells are where multiple routers are strong enough on overlapping channels to compete with each other. Clients there hear too many transmitters at once.',
      },
      {
        q: 'Should I add a router here?',
        a: 'Usually no. In an interference hotspot, a channel change or moving an existing router is often better than adding another radio.',
      },
    ],
    deadzone: [
      {
        q: 'What makes a cell a dead zone?',
        a: 'A dead-zone cell has dropped below the minimum usable signal threshold. In this project that is effectively the no-service part of the heat map.',
      },
      {
        q: 'How do I recover this cluster?',
        a: leadNarrative?.action || 'Look at the cluster center first. That is usually the best place to test a closer router position or a new AP.',
      },
    ],
    priority: [
      {
        q: 'Why are some amber cells more important?',
        a: 'Priority weights tell the planner which spaces matter more. Offices, meeting areas, and other active user zones should generally be fixed before low-impact spaces.',
      },
      {
        q: 'How should this affect optimisation?',
        a: 'Use high-priority amber regions to judge whether a router move is truly better, even if low-priority space gets slightly worse.',
      },
    ],
  }[focusedOverlay] ?? []

  return base
}

export default function OverlayInsightsPanel() {
  const [detailMode, setDetailMode] = useState('simple')
  const [activeChip, setActiveChip] = useState(null)
  const [activeQuestion, setActiveQuestion] = useState(null)
  const state = useStore()
  const {
    focusedOverlay,
    showOverlayInsights,
    setShowOverlayInsights,
    rfExplanations,
  } = state

  const meta = OVERLAY_META[focusedOverlay]
  const content = buildOverlaySummary(state)

  if (!meta || !content) return null

  const leadNarrative = rfExplanations?.narratives?.[0]
  const topicChips = buildTopicChips(focusedOverlay, leadNarrative)
  const hoveredInsight = buildHoveredInsight(state)
  const questions = buildQuestions(focusedOverlay, leadNarrative)
  const simpleCopy = content.explanation
  const technicalCopy = leadNarrative
    ? `${leadNarrative.headline} Average cluster RSSI is ${leadNarrative.avg_signal} dBm and worst-case RSSI is ${leadNarrative.worst_signal} dBm.`
    : content.explanation

  return (
    <section className="oip-wrap" style={{ '--oip-accent': meta.accent }}>
      <div className="oip-toolbar">
        <label className="oip-toggle">
          <input
            type="checkbox"
            checked={showOverlayInsights}
            onChange={(e) => setShowOverlayInsights(e.target.checked)}
          />
          <span>Explain current overlay</span>
        </label>
        <div className="oip-modes">
          <button
            className={`oip-mode ${detailMode === 'simple' ? 'oip-mode--active' : ''}`}
            onClick={() => setDetailMode('simple')}
          >
            Simple
          </button>
          <button
            className={`oip-mode ${detailMode === 'technical' ? 'oip-mode--active' : ''}`}
            onClick={() => setDetailMode('technical')}
          >
            Technical
          </button>
        </div>
      </div>

      {showOverlayInsights && (
        <div className="oip-card">
          <div className="oip-head">
            <strong>{meta.title}</strong>
            <span className="oip-chip">{focusedOverlay}</span>
          </div>
          <p className="oip-copy oip-copy--lead">{meta.intro}</p>
          <div className="oip-section">
            <p className="oip-section-label">Color Meaning</p>
            <div className="oip-legend">
              {meta.legend.map((item) => (
                <div key={item.label} className="oip-legend-item">
                  <span className="oip-swatch" style={{ '--sw': item.color }} />
                  <div className="oip-legend-copy">
                    <p className="oip-stat">{item.label}</p>
                    <p className="oip-copy">{item.meaning}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {topicChips.length > 0 && (
            <div className="oip-chips">
              {topicChips.map((chip) => (
                <button
                  key={chip}
                  className={`oip-topic ${activeChip === chip ? 'oip-topic--active' : ''}`}
                  onClick={() => setActiveChip(current => current === chip ? null : chip)}
                >
                  {chip}
                </button>
              ))}
            </div>
          )}
          <div className="oip-grid">
            {content.stats.map((line) => (
              <div key={line} className="oip-stat-card">
                <p className="oip-stat">{line}</p>
              </div>
            ))}
          </div>
          {activeChip && (
            <div className="oip-section">
              <p className="oip-section-label">Focused Topic</p>
              <p className="oip-copy">
                {activeChip.startsWith('Try ch')
                  ? `This hotspot likely benefits from a lower-conflict channel before moving hardware. ${leadNarrative?.action || ''}`
                  : `${activeChip} is highlighted so the operator can inspect that concern directly on the grid and compare it with the hovered cell below.`}
              </p>
            </div>
          )}
          {questions.length > 0 && (
            <div className="oip-section">
              <p className="oip-section-label">Quick Questions</p>
              <div className="oip-chips">
                {questions.map((item) => (
                  <button
                    key={item.q}
                    className={`oip-topic ${activeQuestion?.q === item.q ? 'oip-topic--active' : ''}`}
                    onClick={() => setActiveQuestion(current => current?.q === item.q ? null : item)}
                  >
                    {item.q}
                  </button>
                ))}
              </div>
              {activeQuestion && (
                <div className="oip-section oip-section--hover">
                  <p className="oip-section-label">Answer</p>
                  <p className="oip-copy">{activeQuestion.a}</p>
                </div>
              )}
            </div>
          )}
          <div className="oip-section">
            <p className="oip-section-label">What This Means</p>
            <p className="oip-copy">{detailMode === 'simple' ? simpleCopy : technicalCopy}</p>
          </div>
          <div className="oip-section">
            <p className="oip-section-label">What To Do Next</p>
            <p className="oip-copy">
              {leadNarrative?.action || 'Use this overlay to decide whether you need a router move, a channel change, or just a closer placement review.'}
            </p>
          </div>
          {hoveredInsight && (
            <div className="oip-section oip-section--hover">
              <p className="oip-section-label">Hovered Cell</p>
              <p className="oip-copy oip-copy--lead">{hoveredInsight.title}</p>
              {hoveredInsight.lines.map((line) => (
                <p key={line} className="oip-copy">{line}</p>
              ))}
            </div>
          )}
          {rfExplanations?.narratives?.[0] && (
            <div className="oip-rf">
              <p className="oip-rf-label">RF explainer</p>
              <p className="oip-copy">{rfExplanations.narratives[0].headline}</p>
              <p className="oip-copy">{rfExplanations.narratives[0].explanation}</p>
            </div>
          )}
        </div>
      )}

      <style>{`
        .oip-wrap {
          display: flex; flex-direction: column; gap: 10px;
          padding: 14px 16px 18px;
          border-top: 1px solid var(--border-mid);
          background: linear-gradient(180deg, rgba(11,14,20,0.75), rgba(11,14,20,0.92));
          max-height: 320px;
          overflow-y: auto;
          flex-shrink: 0;
        }
        .oip-toolbar {
          display: flex; align-items: center; justify-content: space-between; gap: 12px;
          flex-wrap: wrap;
        }
        .oip-toggle {
          display: inline-flex; align-items: center; gap: 8px;
          font-size: 12px; color: var(--text-secondary); user-select: none;
        }
        .oip-toggle input { accent-color: var(--oip-accent); }
        .oip-modes { display: flex; gap: 8px; }
        .oip-mode {
          border: 1px solid var(--border);
          background: var(--bg-surface);
          color: var(--text-secondary);
          border-radius: 999px;
          padding: 6px 12px;
          font-size: 11px;
          cursor: pointer;
        }
        .oip-mode--active {
          border-color: var(--oip-accent);
          color: var(--oip-accent);
          background: color-mix(in srgb, var(--oip-accent) 10%, transparent);
        }
        .oip-card {
          display: flex; flex-direction: column; gap: 6px;
          padding: 16px; border-radius: var(--radius-lg);
          background: var(--bg-surface);
          border: 1px solid color-mix(in srgb, var(--oip-accent) 30%, var(--border));
        }
        .oip-legend {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 10px;
        }
        .oip-legend-item {
          display: flex; gap: 10px; align-items: flex-start;
          padding: 10px;
          border-radius: var(--radius-md);
          background: var(--bg-elevated);
          border: 1px solid var(--border);
        }
        .oip-swatch {
          width: 12px; height: 12px; border-radius: 999px; flex-shrink: 0;
          background: var(--sw);
          margin-top: 3px;
          box-shadow: 0 0 0 2px rgba(255,255,255,0.04);
        }
        .oip-legend-copy {
          display: flex; flex-direction: column; gap: 2px;
        }
        .oip-chips {
          display: flex; flex-wrap: wrap; gap: 8px;
          margin: 4px 0 2px;
        }
        .oip-topic {
          border: 1px solid var(--border);
          background: var(--bg-elevated);
          color: var(--text-secondary);
          border-radius: 999px;
          padding: 6px 10px;
          font-size: 11px;
          cursor: pointer;
        }
        .oip-topic--active {
          border-color: var(--oip-accent);
          color: var(--oip-accent);
          background: color-mix(in srgb, var(--oip-accent) 12%, transparent);
        }
        .oip-head {
          display: flex; align-items: center; justify-content: space-between; gap: 8px;
          color: var(--text-primary); font-size: 11px;
        }
        .oip-chip {
          font-size: 8px; text-transform: uppercase; letter-spacing: 0.08em;
          color: var(--oip-accent); border: 1px solid color-mix(in srgb, var(--oip-accent) 35%, transparent);
          border-radius: 999px; padding: 2px 6px;
        }
        .oip-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px;
          margin-top: 4px;
        }
        .oip-stat-card {
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          padding: 10px;
          background: var(--bg-elevated);
        }
        .oip-section {
          display: flex; flex-direction: column; gap: 5px;
          margin-top: 4px;
        }
        .oip-section--hover {
          padding: 12px;
          border-radius: var(--radius-md);
          border: 1px solid color-mix(in srgb, var(--oip-accent) 24%, var(--border));
          background: color-mix(in srgb, var(--oip-accent) 6%, var(--bg-elevated));
        }
        .oip-stat, .oip-copy, .oip-rf-label, .oip-section-label {
          margin: 0; line-height: 1.55;
        }
        .oip-stat { font-size: 11px; color: var(--text-primary); }
        .oip-copy { font-size: 12px; color: var(--text-secondary); }
        .oip-copy--lead { font-size: 13px; color: var(--text-primary); }
        .oip-section-label {
          font-size: 10px;
          color: var(--oip-accent);
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }
        .oip-rf {
          display: flex; flex-direction: column; gap: 4px;
          margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--border);
        }
        .oip-rf-label {
          font-size: 9px; color: var(--oip-accent);
          text-transform: uppercase; letter-spacing: 0.08em;
        }
      `}</style>
    </section>
  )
}
