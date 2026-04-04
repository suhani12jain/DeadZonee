import React from 'react'
import useStore from '../../store/useStore'
import { useRouters } from '../../hooks/useRouters'

export default function RouterList() {
  const { routers, openRouterModal } = useStore()
  const { removeRouterById } = useRouters()

  if (!routers.length) {
    return (
      <div className="rl-empty">
        <p>No routers placed.</p>
        <p className="rl-hint">Double-click any painted cell with router access to place an AP.</p>
      </div>
    )
  }

  const total = routers.reduce((s, r) => s + (r.cost || 0), 0)

  return (
    <div className="rl-wrap">
      {routers.map(r => (
        <div key={r.router_id} className={`rl-item ${r.is_suggested ? 'rl-ai' : ''}`}>
          <div className="rl-left">
            <span className="rl-dot" style={{ background: r.is_suggested ? 'var(--success)' : 'var(--accent)' }} />
            <div>
              <p className="rl-name">{r.name}</p>
              <p className="rl-meta">[{r.row},{r.col}] · {r.frequency_mhz >= 5000 ? '5GHz' : '2.4GHz'} · ch{r.channel}</p>
            </div>
          </div>
          <div className="rl-right">
            {r.is_suggested && <span className="badge badge-green">AI</span>}
            <span className="rl-cost">₹{r.cost?.toLocaleString()}</span>
            <button className="btn btn-sm" onClick={() => openRouterModal({ ...r, editMode: true })}>✎</button>
          </div>
        </div>
      ))}
      <div className="rl-total">
        <span>{routers.length} routers</span>
        <span style={{ color: 'var(--accent)', fontWeight: 600 }}>₹{total.toLocaleString()}</span>
      </div>

      <style>{`
        .rl-empty { font-size: 11px; color: var(--text-muted); padding: 4px 0; }
        .rl-hint { font-size: 10px; margin-top: 4px; line-height: 1.5; }
        .rl-wrap { display: flex; flex-direction: column; gap: 2px; }
        .rl-item {
          display: flex; align-items: center; justify-content: space-between;
          padding: 8px 10px; border-radius: var(--radius-md);
          border: 1px solid transparent; transition: all 0.12s;
        }
        .rl-item:hover { background: var(--bg-elevated); border-color: var(--border); }
        .rl-ai { border-color: rgba(6,214,160,0.2) !important; }
        .rl-left { display: flex; align-items: center; gap: 8px; }
        .rl-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
        .rl-name { font-size: 11px; color: var(--text-primary); font-family: var(--font-mono); }
        .rl-meta { font-size: 9px; color: var(--text-muted); }
        .rl-right { display: flex; align-items: center; gap: 6px; }
        .rl-cost { font-size: 10px; color: var(--text-secondary); }
        .rl-total {
          display: flex; justify-content: space-between;
          padding: 8px 10px; border-top: 1px solid var(--border);
          margin-top: 4px; font-size: 10px; color: var(--text-muted);
        }
      `}</style>
    </div>
  )
}
