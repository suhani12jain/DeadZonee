import React from 'react'
import useStore from '../../store/useStore'
import { useAnalysis } from '../../hooks/useAnalysis'

const STEP_LABELS = {
  signal:    { label: 'Signal Engine',   icon: '📡' },
  deadzones: { label: 'Dead Zone Detect', icon: '⚫' },
}

export default function AnalysisPreview() {
  const { isAnalysing, analyseSteps, metrics, routers, sessionId } = useStore()
  const { analyse } = useAnalysis()

  const canAnalyse = !!sessionId && routers.length > 0 && !isAnalysing

  return (
    <div className="ap-wrap">
      <button
        className="btn btn-primary btn-full btn-lg"
        onClick={analyse}
        disabled={!canAnalyse}
      >
        {isAnalysing
          ? <><span className="spinner" /> Analysing…</>
          : '▶ Run Analysis'}
      </button>

      {routers.length === 0 && (
        <p className="ap-hint">Place at least one router before analysing.</p>
      )}

      {/* Step progress */}
      {analyseSteps.length > 0 && (
        <div className="ap-steps">
          {analyseSteps.map((step, i) => (
            <div key={i} className={`ap-step ap-step--${step.status}`}>
              <span className="ap-step-icon">
                {step.status === 'done' ? '✓' : step.status === 'error' ? '✗' : '…'}
              </span>
              <span className="ap-step-label">
                {STEP_LABELS[step.step]?.label ?? step.step}
              </span>
              {step.status === 'error' && step.detail && (
                <span className="ap-step-err" title={step.detail}>!</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Quick metrics summary */}
      {metrics && (
        <div className="ap-summary">
          <div className="ap-sm-item">
            <span className="ap-sm-val" style={{ color: metrics.coverage_pct >= 80 ? 'var(--success)' : 'var(--warning)' }}>
              {metrics.coverage_pct?.toFixed(1)}%
            </span>
            <span className="ap-sm-key">Coverage</span>
          </div>
          <div className="ap-sm-item">
            <span className="ap-sm-val" style={{ color: 'var(--danger)' }}>
              {metrics.dead_zone_count ?? '—'}
            </span>
            <span className="ap-sm-key">Dead cells</span>
          </div>
          <div className="ap-sm-item">
            <span className="ap-sm-val">{metrics.avg_signal?.toFixed(0)} <small>dBm</small></span>
            <span className="ap-sm-key">Avg signal</span>
          </div>
        </div>
      )}

      <style>{`
        .ap-wrap { display: flex; flex-direction: column; gap: 10px; }
        .ap-hint { font-size: 10px; color: var(--text-muted); line-height: 1.5; }
        .ap-steps { display: flex; flex-direction: column; gap: 4px; }
        .ap-step {
          display: flex; align-items: center; gap: 7px;
          font-size: 10px; padding: 5px 8px; border-radius: var(--radius-md);
          border: 1px solid var(--border);
        }
        .ap-step--done { border-color: rgba(6,214,160,0.25); color: var(--success); }
        .ap-step--error { border-color: rgba(255,77,109,0.25); color: var(--danger); }
        .ap-step--running { border-color: var(--border-bright); color: var(--accent); }
        .ap-step-icon { font-size: 11px; width: 14px; text-align: center; }
        .ap-step-label { flex: 1; }
        .ap-step-err { color: var(--warning); cursor: help; }
        .ap-summary {
          display: grid; grid-template-columns: 1fr 1fr 1fr;
          gap: 6px; margin-top: 4px;
        }
        .ap-sm-item {
          background: var(--bg-elevated); border: 1px solid var(--border);
          border-radius: var(--radius-md); padding: 8px 6px;
          display: flex; flex-direction: column; align-items: center; gap: 2px;
        }
        .ap-sm-val { font-size: 14px; font-weight: 700; font-family: var(--font-display); }
        .ap-sm-key { font-size: 8px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
      `}</style>
    </div>
  )
}
