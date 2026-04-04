import React from 'react'
import useStore from '../../store/useStore'
import { signalColor } from '../../constants/zoneConfig'

function MetricRow({ label, value, unit, color }) {
  return (
    <div className="mr-row">
      <span className="mr-label">{label}</span>
      <span className="mr-value" style={{ color: color ?? 'var(--text-primary)' }}>
        {value ?? '—'}{unit ? <span className="mr-unit"> {unit}</span> : null}
      </span>
    </div>
  )
}

export default function MetricsSidebar() {
  const { metrics, deadZoneCount, clusters, overlays, overlayOpacity, toggleOverlay, setOpacity } = useStore()

  const m = metrics ?? {}

  return (
    <div className="ms-wrap">
      <p className="section-label">Signal Metrics</p>
      <div className="ms-metrics">
        <MetricRow label="Coverage" value={m.coverage_pct?.toFixed(1)} unit="%" color={
          m.coverage_pct >= 90 ? 'var(--sig-excellent)' :
          m.coverage_pct >= 70 ? 'var(--sig-good)' : 'var(--sig-poor)'
        } />
        <MetricRow label="Avg Signal" value={m.avg_signal?.toFixed(1)} unit="dBm"
          color={signalColor(m.avg_signal ?? -100)} />
        <MetricRow label="Worst Signal" value={m.worst_signal?.toFixed(1)} unit="dBm"
          color={signalColor(m.worst_signal ?? -100)} />
        <MetricRow label="Interference" value={m.interference_score?.toFixed(3)} />
        <MetricRow label="Dead Zones" value={deadZoneCount}
          color={deadZoneCount > 0 ? 'var(--danger)' : 'var(--success)'} />
        <MetricRow label="Clusters" value={clusters?.length} />
        <MetricRow label="Est. Cost" value={m.estimated_cost ? `₹${m.estimated_cost.toLocaleString()}` : null} />
      </div>

      <div className="divider" />

      {/* Overlay toggles */}
      <p className="section-label">Overlays</p>
      <div className="ms-overlays">
        {[
          { key: 'zones',        label: 'Zone Colours',  color: '#63b3ed' },
          { key: 'heatmap',      label: 'Signal Heat',   color: '#10b981' },
          { key: 'deadzone',     label: 'Dead Zones',    color: '#ef4444' },
          { key: 'interference', label: 'Interference',  color: '#a855f7' },
          { key: 'priority',     label: 'Priority Wt.',  color: '#f59e0b' },
        ].map(({ key, label, color }) => (
          <button key={key}
            className={`ov-btn ${overlays[key] ? 'ov-active' : ''}`}
            style={{ '--oc': color }}
            onClick={() => toggleOverlay(key)}
          >
            <span className="ov-dot" />
            {label}
          </button>
        ))}
      </div>

      <div className="divider" />
      <p className="section-label">Opacity</p>
      <input type="range" min={10} max={100} value={Math.round(overlayOpacity * 100)}
        onChange={e => setOpacity(parseInt(e.target.value) / 100)}
        style={{ width: '100%', accentColor: 'var(--accent)' }} />
      <p style={{ fontSize: '9px', color: 'var(--text-muted)', textAlign: 'right' }}>
        {Math.round(overlayOpacity * 100)}%
      </p>

      <style>{`
        .ms-wrap { display: flex; flex-direction: column; gap: 8px; }
        .ms-metrics { display: flex; flex-direction: column; gap: 6px; }
        .mr-row { display: flex; justify-content: space-between; align-items: center; }
        .mr-label { font-size: 10px; color: var(--text-muted); }
        .mr-value { font-size: 11px; font-weight: 600; }
        .mr-unit { font-size: 9px; font-weight: 400; color: var(--text-muted); }

        .ms-overlays { display: flex; flex-direction: column; gap: 3px; }
        .ov-btn {
          display: flex; align-items: center; gap: 7px;
          padding: 6px 9px; border-radius: var(--radius-md);
          border: 1px solid transparent; background: transparent;
          cursor: pointer; font-size: 10px; color: var(--text-muted);
          font-family: var(--font-mono); transition: all 0.12s; text-align: left;
        }
        .ov-btn:hover { background: var(--bg-elevated); color: var(--text-primary); }
        .ov-active { background: var(--bg-elevated); border-color: var(--oc); color: var(--oc) !important; }
        .ov-dot {
          width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
          background: var(--oc); opacity: 0.4;
        }
        .ov-active .ov-dot { opacity: 1; box-shadow: 0 0 6px var(--oc); }
      `}</style>
    </div>
  )
}
