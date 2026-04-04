import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import useStore from '../../store/useStore'
import { useAnalysis } from '../../hooks/useAnalysis'

export default function OptimizationPanel() {
  const { optimResult, isOptimising, sessionId, signalMatrix } = useStore()
  const { optimise, suggest, acceptAndReanalyse, isSuggesting, suggestion } = useAnalysis()

  // Rebuild from store since useAnalysis destructures from hook
  const storeState = useStore()
  const isSug = storeState.isSuggesting
  const sug   = storeState.suggestion

  const canOpt = !!sessionId && !!signalMatrix && !isOptimising

  // Score history chart data
  const histData = optimResult?.score_history?.map((v, i) => ({ i: i + 1, score: parseFloat(v.toFixed(2)) })) ?? []

  return (
    <div className="op-wrap">

      {/* Optimise button */}
      <div className="op-section">
        <p className="section-label">Auto Optimise</p>
        <button className="btn btn-warning btn-full" onClick={optimise} disabled={!canOpt}>
          {isOptimising ? <><span className="spinner" /> Optimising…</> : '⚡ Run PSO + SA'}
        </button>
        {!signalMatrix && <p className="op-hint">Run analysis first.</p>}
      </div>

      {/* Optimisation results */}
      {optimResult && (
        <div className="op-result fade-up">
          <div className="op-scores">
            <div className="op-score-item">
              <span className="op-score-label">Before</span>
              <span className="op-score-val" style={{ color: 'var(--sig-poor)' }}>
                {optimResult.original_score?.toFixed(1)}
              </span>
            </div>
            <span className="op-arrow">→</span>
            <div className="op-score-item">
              <span className="op-score-label">After</span>
              <span className="op-score-val" style={{ color: 'var(--success)' }}>
                {optimResult.optimised_score?.toFixed(1)}
              </span>
            </div>
            <div className="op-score-item">
              <span className="op-score-label">Gain</span>
              <span className="op-score-val" style={{ color: 'var(--warning)' }}>
                +{optimResult.improvement_pct?.toFixed(1)}%
              </span>
            </div>
          </div>
          <p className="op-algo">Algorithm: <strong>{optimResult.algorithm}</strong></p>

          {histData.length > 0 && (
            <div className="op-chart">
              <ResponsiveContainer width="100%" height={90}>
                <BarChart data={histData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                  <XAxis dataKey="i" tick={{ fontSize: 8, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 8, fill: 'var(--text-muted)' }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                    itemStyle={{ color: 'var(--accent)' }}
                  />
                  <Bar dataKey="score" radius={[2, 2, 0, 0]}>
                    {histData.map((_, i) => (
                      <Cell key={i} fill={i === histData.length - 1 ? 'var(--success)' : 'var(--accent)'} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      <div className="divider" />

      {/* AI Suggester */}
      <div className="op-section">
        <p className="section-label">AI Investigator</p>
        <button className="btn btn-success btn-full" onClick={suggest} disabled={isSug || !sessionId}>
          {isSug ? <><span className="spinner" /> Thinking…</> : '🤖 Suggest Router'}
        </button>
      </div>

      {/* Suggestion card */}
      {sug && (
        <div className="sug-card fade-up">
          <div className="sug-loc">
            <span className="badge badge-green">AI Suggestion</span>
            <span className="sug-coords">Row {sug.suggested_row}, Col {sug.suggested_col}</span>
          </div>
          <p className="sug-gain">
            Coverage gain: <strong>+{sug.coverage_gain_pct?.toFixed(1)}%</strong>
          </p>
          {sug.explanation && (
            <p className="sug-text">"{sug.explanation}"</p>
          )}
          {sug.suggested_config && (
            <p className="sug-cfg">
              {sug.suggested_config.frequency ?? 2400}MHz · ch{sug.suggested_config.channel} · {sug.suggested_config.tx_power ?? 20}dBm
            </p>
          )}
          <button className="btn btn-success btn-sm btn-full"
            onClick={() => acceptAndReanalyse(sug.suggestion_id)}>
            ✓ Accept &amp; Re-analyse
          </button>
        </div>
      )}

      <style>{`
        .op-wrap { display: flex; flex-direction: column; gap: 10px; }
        .op-section { display: flex; flex-direction: column; gap: 6px; }
        .op-hint { font-size: 9px; color: var(--text-muted); }
        .op-result { display: flex; flex-direction: column; gap: 8px; }
        .op-scores { display: flex; align-items: center; gap: 8px; }
        .op-score-item { display: flex; flex-direction: column; align-items: center; gap: 1px; flex: 1; }
        .op-score-label { font-size: 8px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
        .op-score-val { font-size: 16px; font-weight: 700; font-family: var(--font-display); }
        .op-arrow { font-size: 14px; color: var(--text-muted); }
        .op-algo { font-size: 9px; color: var(--text-muted); }
        .op-chart { margin-top: 2px; }

        .sug-card {
          background: var(--bg-elevated);
          border: 1px solid rgba(6,214,160,0.25);
          border-radius: var(--radius-lg);
          padding: 12px; display: flex; flex-direction: column; gap: 7px;
        }
        .sug-loc { display: flex; align-items: center; gap: 8px; }
        .sug-coords { font-size: 10px; color: var(--text-secondary); }
        .sug-gain { font-size: 11px; color: var(--text-primary); }
        .sug-text {
          font-size: 10px; color: var(--text-secondary); line-height: 1.6;
          font-style: italic; border-left: 2px solid rgba(6,214,160,0.3); padding-left: 8px;
        }
        .sug-cfg { font-size: 9px; color: var(--accent); font-family: var(--font-mono); }
      `}</style>
    </div>
  )
}
