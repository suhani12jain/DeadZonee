import React from 'react'
import { ZONE_CONFIG, ZONE_KEYS } from '../../constants/zoneConfig'
import useStore from '../../store/useStore'

/**
 * ZoneLabels — zone type picker panel.
 * Click to select active zone for painting.
 */
export default function ZoneLabels() {
  const { activeZone, setActiveZone, activeTool, setActiveTool } = useStore()

  return (
    <div className="zone-labels">
      <p className="section-label">Zone Types</p>

      {/* Tool selector */}
      <div className="tool-row">
        {[
          { key: 'paint',  icon: '✎', label: 'Paint' },
          { key: 'erase',  icon: '◻', label: 'Erase' },
        ].map(t => (
          <button
            key={t.key}
            className={`btn btn-sm ${activeTool === t.key ? 'btn-primary' : ''}`}
            onClick={() => setActiveTool(t.key)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="divider" />

      {/* Zone grid */}
      <div className="zone-grid">
        {ZONE_KEYS.map(key => {
          const z = ZONE_CONFIG[key]
          const active = activeZone === key
          return (
            <button
              key={key}
              className={`zone-btn ${active ? 'zone-btn--active' : ''}`}
              style={{ '--zcolor': z.color }}
              onClick={() => { setActiveZone(key); setActiveTool('paint') }}
            >
              <span className="zone-dot" />
              <span className="zone-name">{z.label}</span>
              <span className="zone-atten">{z.attenuation === 99 ? '∞' : z.attenuation}dB</span>
              {!z.allow_router && <span className="zone-no-router">⊘</span>}
            </button>
          )
        })}
      </div>

      <div className="divider" />
      <div className="zone-legend">
        <span className="zl-item"><span style={{ color: 'var(--text-muted)' }}>⊘</span> Router not allowed</span>
        <span className="zl-item"><span style={{ color: 'var(--accent)' }}>dB</span> Attenuation</span>
      </div>

      <style>{`
        .zone-labels { display: flex; flex-direction: column; gap: 8px; padding: 0 2px; }
        .tool-row { display: flex; gap: 6px; }
        .zone-grid { display: flex; flex-direction: column; gap: 2px; }
        .zone-btn {
          display: flex; align-items: center; gap: 8px;
          padding: 7px 10px;
          border: 1px solid transparent;
          border-radius: var(--radius-md);
          background: transparent;
          cursor: pointer;
          transition: all 0.12s;
          text-align: left;
          width: 100%;
        }
        .zone-btn:hover { background: var(--bg-elevated); border-color: var(--border); }
        .zone-btn--active {
          background: var(--bg-elevated);
          border-color: var(--zcolor);
          box-shadow: inset 0 0 0 1px var(--zcolor), 0 0 12px rgba(var(--zcolor), 0.1);
        }
        .zone-dot {
          width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
          background: var(--zcolor);
          box-shadow: 0 0 6px var(--zcolor);
        }
        .zone-name {
          font-size: 11px; color: var(--text-primary); flex: 1;
          font-family: var(--font-mono);
        }
        .zone-btn--active .zone-name { color: var(--zcolor); }
        .zone-atten { font-size: 9px; color: var(--text-muted); }
        .zone-no-router { font-size: 9px; color: var(--danger); }
        .zone-legend { display: flex; flex-direction: column; gap: 4px; }
        .zl-item { font-size: 9px; color: var(--text-muted); }
      `}</style>
    </div>
  )
}
