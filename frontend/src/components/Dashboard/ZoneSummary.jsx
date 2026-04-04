import React, { useMemo } from 'react'
import useStore from '../../store/useStore'
import { ZONE_CONFIG } from '../../constants/zoneConfig'

export default function ZoneSummary() {
  const { cells, gridMeta } = useStore()

  const summary = useMemo(() => {
    if (!cells.length) return []
    const counts = {}
    cells.forEach(c => { counts[c.zone_type] = (counts[c.zone_type] ?? 0) + 1 })
    return Object.entries(counts)
      .map(([type, count]) => ({ type, count, cfg: ZONE_CONFIG[type] }))
      .filter(e => e.cfg)
      .sort((a, b) => b.count - a.count)
  }, [cells])

  const total = cells.length

  if (!summary.length) return (
    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>No zones painted yet.</div>
  )

  const csm = gridMeta?.cell_size_m ?? 1

  return (
    <div className="zs-wrap">
      <p className="section-label">Zone Coverage</p>
      {summary.map(({ type, count, cfg }) => (
        <div key={type} className="zs-row">
          <span className="zs-dot" style={{ background: cfg.color }} />
          <span className="zs-label">{cfg.label}</span>
          <div className="zs-bar-wrap">
            <div className="zs-bar" style={{ width: `${(count / total) * 100}%`, background: cfg.color }} />
          </div>
          <span className="zs-count">{(count * csm * csm).toFixed(0)}m²</span>
        </div>
      ))}
      <style>{`
        .zs-wrap { display: flex; flex-direction: column; gap: 5px; }
        .zs-row { display: flex; align-items: center; gap: 6px; }
        .zs-dot { width: 7px; height: 7px; border-radius: 1px; flex-shrink: 0; }
        .zs-label { font-size: 9px; color: var(--text-secondary); width: 80px; flex-shrink: 0; }
        .zs-bar-wrap { flex: 1; height: 4px; background: var(--bg-highlight); border-radius: 2px; overflow: hidden; }
        .zs-bar { height: 100%; border-radius: 2px; transition: width 0.3s; opacity: 0.7; }
        .zs-count { font-size: 9px; color: var(--text-muted); width: 36px; text-align: right; flex-shrink: 0; }
      `}</style>
    </div>
  )
}
