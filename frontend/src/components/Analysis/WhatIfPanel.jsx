import React, { useState } from 'react'
import useStore from '../../store/useStore'
import { runWhatIf } from '../../api/apiClient'
import { getZone } from '../../constants/zoneConfig'

/**
 * What-If Agent — NL + manual cells, runs /api/what-if, never saves the floor plan.
 */
export default function WhatIfPanel() {
  const {
    sessionId,
    hoveredCell,
    activeZone,
    whatIf,
    whatIfViewMode,
    whatIfLoading,
    whatIfManualCells,
    setWhatIf,
    clearWhatIf,
    setWhatIfViewMode,
    setWhatIfLoading,
    addWhatIfManualCell,
    removeWhatIfManualCell,
    clearWhatIfManualCells,
    pushToast,
    toggleOverlay,
    overlays,
  } = useStore()

  const [query, setQuery] = useState('')

  const run = async () => {
    const q = query.trim()
    if (!sessionId) {
      pushToast('Create a session first', 'warning')
      return
    }
    if (!q && whatIfManualCells.length === 0) {
      pushToast('Type a scenario or add at least one cell', 'warning')
      return
    }
    setWhatIfLoading(true)
    try {
      const body = {
        session_id: sessionId,
        ...(q ? { query: q } : {}),
        ...(whatIfManualCells.length
          ? {
              manual_changes: whatIfManualCells.map((c) => ({
                row: c.row,
                col: c.col,
                zone_type: c.zone_type,
              })),
            }
          : {}),
      }
      const data = await runWhatIf(body)
      const { status, ...rest } = data
      setWhatIf(rest)
      if (!overlays.whatif) toggleOverlay('whatif')
      pushToast('What-if preview ready (not saved)', 'success')
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'What-if failed'
      pushToast(typeof msg === 'string' ? msg : JSON.stringify(msg), 'error')
    } finally {
      setWhatIfLoading(false)
    }
  }

  const addHovered = () => {
    if (!hoveredCell) {
      pushToast('Hover a cell on the grid first', 'warning')
      return
    }
    addWhatIfManualCell(hoveredCell.row, hoveredCell.col, activeZone)
    pushToast(`Queued [${hoveredCell.row},${hoveredCell.col}] as ${getZone(activeZone).label}`, 'info')
  }

  return (
    <div className="whatif-panel">
      <p className="whatif-hint">
        Try changes in memory only. Your saved grid in MongoDB is never updated.
        Free-form English needs <code>ANTHROPIC_KEY</code> in <code>backend/.env</code>; without
        it, clear the box below and use <b>Add hovered cell</b>, or use short phrases like
        “concrete wall row 3” (offline parser).
      </p>

      <label className="whatif-label">Describe a change (English)</label>
      <textarea
        className="whatif-textarea"
        rows={3}
        placeholder='e.g. "add a concrete wall along row 5 from column 0 to 12"'
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={whatIfLoading}
      />

      <div className="whatif-manual">
        <span className="whatif-label">Or queue cells (uses active zone from Zone Painter)</span>
        <div className="whatif-row">
          <button type="button" className="btn btn-sm" onClick={addHovered} disabled={whatIfLoading}>
            Add hovered cell
          </button>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => clearWhatIfManualCells()}
            disabled={!whatIfManualCells.length}
          >
            Clear queue
          </button>
        </div>
        {whatIfManualCells.length > 0 && (
          <ul className="whatif-queue">
            {whatIfManualCells.map((c) => (
              <li key={`${c.row}_${c.col}`}>
                [{c.row},{c.col}] → {getZone(c.zone_type).label}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => removeWhatIfManualCell(c.row, c.col)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <button type="button" className="btn btn-sm btn-primary whatif-run" onClick={run} disabled={whatIfLoading}>
        {whatIfLoading ? 'Running…' : 'Run what-if'}
      </button>

      {whatIf && (
        <div className="whatif-results">
          <div className="whatif-view-toggle">
            <span className="whatif-label">Overlay</span>
            <div className="seg">
              {[
                ['delta', 'Δ signal'],
                ['new_dead', 'New dead'],
                ['recovered', 'Recovered'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`seg-btn ${whatIfViewMode === id ? 'on' : ''}`}
                  onClick={() => setWhatIfViewMode(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <label className="whatif-check">
            <input
              type="checkbox"
              checked={!!overlays.whatif}
              onChange={() => toggleOverlay('whatif')}
            />
            Show preview on canvas
          </label>

          {whatIf.summary && (
            <dl className="whatif-stats">
              <dt>Coverage</dt>
              <dd>
                {whatIf.summary.coverage_before_pct}% → {whatIf.summary.coverage_after_pct}%
              </dd>
              <dt>New dead cells</dt>
              <dd>{whatIf.summary.new_dead_cells}</dd>
              <dt>Recovered</dt>
              <dd>{whatIf.summary.recovered_dead_cells}</dd>
            </dl>
          )}

          {whatIf.explanation && <p className="whatif-explain">{whatIf.explanation}</p>}

          {whatIf.applied_changes?.length > 0 && (
            <details className="whatif-details">
              <summary>Applied patches ({whatIf.applied_changes.length})</summary>
              <pre>{JSON.stringify(whatIf.applied_changes, null, 2)}</pre>
            </details>
          )}

          <button type="button" className="btn btn-sm btn-ghost" onClick={() => clearWhatIf()}>
            Dismiss preview
          </button>
        </div>
      )}

      <style>{`
        .whatif-panel { font-size: 11px; color: var(--text-secondary); }
        .whatif-hint { margin: 0 0 10px; line-height: 1.45; opacity: 0.9; }
        .whatif-label {
          display: block; font-size: 9px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.06em;
          color: var(--text-muted); margin-bottom: 4px;
        }
        .whatif-textarea {
          width: 100%; resize: vertical; min-height: 56px;
          background: var(--bg-base); border: 1px solid var(--border-mid);
          border-radius: var(--radius-sm); color: var(--text-primary);
          padding: 8px; font-family: var(--font-sans); font-size: 11px;
          margin-bottom: 10px;
        }
        .whatif-manual { margin-bottom: 10px; }
        .whatif-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
        .whatif-queue {
          list-style: none; margin: 8px 0 0; padding: 0;
          max-height: 88px; overflow-y: auto;
        }
        .whatif-queue li {
          display: flex; align-items: center; justify-content: space-between;
          padding: 3px 6px; background: var(--bg-elevated);
          border-radius: var(--radius-sm); margin-bottom: 3px;
          font-family: var(--font-mono); font-size: 10px;
        }
        .link-btn {
          background: none; border: none; color: var(--danger);
          cursor: pointer; font-size: 14px; line-height: 1; padding: 0 4px;
        }
        .whatif-run { width: 100%; margin-bottom: 4px; }
        .whatif-results {
          margin-top: 12px; padding-top: 10px;
          border-top: 1px solid var(--border-mid);
        }
        .whatif-view-toggle { margin-bottom: 8px; }
        .seg { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
        .seg-btn {
          flex: 1; min-width: 0; padding: 4px 6px; font-size: 9px;
          background: var(--bg-base); border: 1px solid var(--border-mid);
          border-radius: var(--radius-sm); color: var(--text-muted);
          cursor: pointer;
        }
        .seg-btn.on {
          border-color: var(--accent); color: var(--accent);
          background: rgba(99,179,237,0.08);
        }
        .whatif-check { display: flex; align-items: center; gap: 6px; margin: 8px 0; cursor: pointer; }
        .whatif-stats {
          display: grid; grid-template-columns: 1fr auto; gap: 4px 10px;
          margin: 8px 0; font-family: var(--font-mono); font-size: 10px;
        }
        .whatif-stats dt { color: var(--text-muted); }
        .whatif-stats dd { margin: 0; text-align: right; color: var(--text-primary); }
        .whatif-explain {
          margin: 10px 0; line-height: 1.5; color: var(--text-primary);
          font-size: 11px;
        }
        .whatif-details { margin: 8px 0; }
        .whatif-details pre {
          font-size: 9px; overflow: auto; max-height: 120px;
          background: var(--bg-base); padding: 6px; border-radius: var(--radius-sm);
        }
      `}</style>
    </div>
  )
}
