import React, { useState } from 'react'
import { downloadReport, getReportUrl } from '../../api/apiClient'
import useStore from '../../store/useStore'

export default function ReportGenerator() {
  const { sessionId, projectName, metrics, pushToast } = useStore()
  const [loading, setLoading] = useState(false)

  const handleDownload = async () => {
    if (!sessionId) { pushToast('No active session', 'error'); return }
    setLoading(true)
    try {
      const blob = await downloadReport(sessionId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `DeadZero_${projectName.replace(/\s+/g, '_')}_${sessionId.slice(0, 6)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      pushToast('Report downloaded', 'success')
    } catch (err) {
      pushToast('Report failed: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rg-wrap">
      <p className="section-label">Export Report</p>
      <p className="rg-desc">
        Generates a PDF with floor plan metrics, signal heatmap, router config, and AI suggestions.
      </p>

      {metrics ? (
        <div className="rg-summary">
          <div className="rg-sm">
            <span>{metrics.coverage_pct?.toFixed(1)}%</span>
            <span>Coverage</span>
          </div>
          <div className="rg-sm">
            <span>{metrics.dead_zone_count ?? '—'}</span>
            <span>Dead cells</span>
          </div>
          <div className="rg-sm">
            <span>₹{metrics.estimated_cost?.toLocaleString() ?? '—'}</span>
            <span>Est. cost</span>
          </div>
        </div>
      ) : (
        <p className="rg-nodata">Run analysis to populate report data.</p>
      )}

      <button className="btn btn-primary btn-full" onClick={handleDownload} disabled={loading || !sessionId}>
        {loading ? <><span className="spinner" /> Generating…</> : '⬇ Download PDF Report'}
      </button>

      {sessionId && (
        <a className="rg-link" href={getReportUrl(sessionId)} target="_blank" rel="noopener noreferrer">
          Open in new tab ↗
        </a>
      )}

      <style>{`
        .rg-wrap { display: flex; flex-direction: column; gap: 10px; }
        .rg-desc { font-size: 10px; color: var(--text-muted); line-height: 1.6; }
        .rg-nodata { font-size: 10px; color: var(--text-muted); }
        .rg-summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
        .rg-sm {
          background: var(--bg-elevated); border: 1px solid var(--border);
          border-radius: var(--radius-md); padding: 8px 6px;
          display: flex; flex-direction: column; align-items: center; gap: 2px;
          font-family: var(--font-mono);
        }
        .rg-sm span:first-child { font-size: 12px; font-weight: 700; color: var(--accent); }
        .rg-sm span:last-child  { font-size: 8px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
        .rg-link { font-size: 10px; color: var(--accent); text-decoration: none; text-align: center; }
        .rg-link:hover { text-decoration: underline; }
      `}</style>
    </div>
  )
}
