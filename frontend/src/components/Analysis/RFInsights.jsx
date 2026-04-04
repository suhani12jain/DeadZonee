import React from 'react'
import useStore from '../../store/useStore'

function SeverityBadge({ severity }) {
  const color =
    severity === 'critical' ? 'var(--danger)' :
    severity === 'high' ? 'var(--warning)' :
    'var(--accent)'

  return (
    <span className="rfi-sev" style={{ '--sev': color }}>
      {severity}
    </span>
  )
}

export default function RFInsights({ compact = false, maxItems = null }) {
  const { rfExplanations } = useStore()
  const narratives = rfExplanations?.narratives ?? []
  const items = maxItems ? narratives.slice(0, maxItems) : narratives

  if (!rfExplanations) return null

  return (
    <div className="rfi-wrap">
      {rfExplanations.summary && (
        <p className="rfi-summary">{rfExplanations.summary}</p>
      )}

      {items.length > 0 ? (
        <div className="rfi-list">
          {items.map((item) => (
            <article key={item.cluster_id} className={`rfi-card ${compact ? 'rfi-card--compact' : ''}`}>
              <div className="rfi-head">
                <strong className="rfi-title">{item.title}</strong>
                <SeverityBadge severity={item.severity} />
              </div>
              <p className="rfi-headline">{item.headline}</p>
              <p className="rfi-copy">{item.explanation}</p>
              <p className="rfi-action">{item.action}</p>
              {!compact && (
                <div className="rfi-meta">
                  <span>RSSI {item.avg_signal?.toFixed?.(1) ?? item.avg_signal} dBm</span>
                  <span>Worst {item.worst_signal?.toFixed?.(1) ?? item.worst_signal} dBm</span>
                  <span>Intf {item.avg_interference?.toFixed?.(2) ?? item.avg_interference}</span>
                  <span>Row {item.centroid_row}, Col {item.centroid_col}</span>
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <p className="rfi-empty">No weak clusters remain large enough to explain.</p>
      )}

      <style>{`
        .rfi-wrap { display: flex; flex-direction: column; gap: 8px; }
        .rfi-summary {
          margin: 0; font-size: 10px; line-height: 1.6;
          color: var(--text-secondary);
        }
        .rfi-list { display: flex; flex-direction: column; gap: 7px; }
        .rfi-card {
          display: flex; flex-direction: column; gap: 5px;
          padding: 10px; border-radius: var(--radius-md);
          background: var(--bg-elevated); border: 1px solid var(--border);
        }
        .rfi-card--compact { padding: 9px; gap: 4px; }
        .rfi-head {
          display: flex; align-items: center; justify-content: space-between; gap: 8px;
        }
        .rfi-title { font-size: 10px; color: var(--text-primary); }
        .rfi-sev {
          font-size: 8px; text-transform: uppercase; letter-spacing: 0.08em;
          color: var(--sev); border: 1px solid color-mix(in srgb, var(--sev) 35%, transparent);
          border-radius: 999px; padding: 2px 6px;
        }
        .rfi-headline, .rfi-copy, .rfi-action, .rfi-empty {
          margin: 0; font-size: 9px; line-height: 1.55;
        }
        .rfi-headline { color: var(--text-primary); }
        .rfi-copy { color: var(--text-secondary); }
        .rfi-action { color: var(--accent); font-family: var(--font-mono); }
        .rfi-meta {
          display: flex; flex-wrap: wrap; gap: 6px;
          font-size: 8px; color: var(--text-muted);
          font-family: var(--font-mono);
        }
      `}</style>
    </div>
  )
}
