import React from 'react'
import useStore from '../../store/useStore'
import { getZone, signalColor, signalLabel } from '../../constants/zoneConfig'

/**
 * CellInfoPanel — shows live info about the currently hovered cell.
 */
export default function CellInfoPanel() {
  const { hoveredCell, cells, signalMatrix, qualityMatrix, interferenceMatrix } = useStore()

  if (!hoveredCell) {
    return (
      <div className="cip-empty">
        <span>Hover a cell to inspect</span>
      </div>
    )
  }

  const { row, col } = hoveredCell
  const cell = cells.find(c => c.row === row && c.col === col)
  const zone = cell ? getZone(cell.zone_type) : null
  const signal = signalMatrix?.[row]?.[col]
  const quality = qualityMatrix?.[row]?.[col]
  const interference = interferenceMatrix?.[row]?.[col]

  return (
    <div className="cip fade-up">
      <p className="section-label">Cell Inspector</p>
      <div className="cip-coords">
        <span className="cip-rc">Row {row}</span>
        <span className="cip-sep">·</span>
        <span className="cip-rc">Col {col}</span>
      </div>

      {cell && zone && (
        <div className="cip-zone" style={{ '--zc': zone.color }}>
          <span className="cip-zdot" />
          <span className="cip-zlabel">{zone.label}</span>
          <span className="cip-zatten">{zone.attenuation === 99 ? '∞' : zone.attenuation} dB</span>
        </div>
      )}

      {signal !== undefined && signal !== null && (
        <div className="cip-rows">
          <div className="cip-row">
            <span className="cip-key">Signal</span>
            <span className="cip-val" style={{ color: signalColor(signal) }}>
              {signal.toFixed(1)} dBm
            </span>
          </div>
          <div className="cip-row">
            <span className="cip-key">Quality</span>
            <span className="cip-val" style={{ color: signalColor(signal) }}>
              {quality ?? signalLabel(signal)}
            </span>
          </div>
          {interference !== undefined && (
            <div className="cip-row">
              <span className="cip-key">Interference</span>
              <span className="cip-val" style={{ color: interference > 0.5 ? 'var(--danger)' : 'var(--text-secondary)' }}>
                {interference.toFixed(2)}
              </span>
            </div>
          )}
          <div className="cip-row">
            <span className="cip-key">Priority wt.</span>
            <span className="cip-val">{cell?.priority_weight ?? '—'}</span>
          </div>
          <div className="cip-row">
            <span className="cip-key">Router</span>
            <span className="cip-val" style={{ color: cell?.allow_router ? 'var(--success)' : 'var(--danger)' }}>
              {cell?.allow_router ? 'Allowed' : 'Blocked'}
            </span>
          </div>
        </div>
      )}

      <style>{`
        .cip { display: flex; flex-direction: column; gap: 8px; }
        .cip-empty { font-size: 10px; color: var(--text-muted); padding: 6px 2px; }
        .cip-coords { display: flex; align-items: center; gap: 6px; }
        .cip-rc { font-size: 13px; font-weight: 600; color: var(--accent); }
        .cip-sep { color: var(--text-muted); }
        .cip-zone {
          display: flex; align-items: center; gap: 7px;
          background: var(--bg-elevated); border: 1px solid var(--border);
          border-left: 3px solid var(--zc, var(--accent));
          border-radius: var(--radius-md); padding: 6px 10px;
        }
        .cip-zdot { width: 8px; height: 8px; border-radius: 2px; background: var(--zc); flex-shrink:0; }
        .cip-zlabel { font-size: 11px; color: var(--text-primary); flex: 1; }
        .cip-zatten { font-size: 10px; color: var(--text-muted); }
        .cip-rows { display: flex; flex-direction: column; gap: 4px; }
        .cip-row { display: flex; justify-content: space-between; align-items: center; }
        .cip-key { font-size: 10px; color: var(--text-muted); }
        .cip-val { font-size: 10px; font-weight: 600; }
      `}</style>
    </div>
  )
}
