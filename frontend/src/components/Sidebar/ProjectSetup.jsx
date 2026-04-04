import React, { useState } from 'react'
import { createSession } from '../../api/apiClient'
import { useGrid } from '../../hooks/useGrid'
import useStore from '../../store/useStore'

function apiErrorMessage(err) {
  const isNetwork =
    err?.code === 'ERR_NETWORK' ||
    err?.message === 'Network Error' ||
    (!err?.response && err?.request)
  if (isNetwork) {
    return (
      'Cannot reach the API. Start the backend on port 8000 (e.g. uvicorn from backend/) ' +
      'and ensure MongoDB is running. If you use `npm run dev`, requests go through the Vite proxy to localhost:8000.'
    )
  }
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join('; ') || err.message
  }
  return err?.message || 'Request failed'
}

export default function ProjectSetup() {
  const [form, setForm] = useState({
    projectName:  '',
    buildingName: '',
    widthM:       30,
    heightM:      20,
    cellSizeM:    2,
  })
  const [loading, setLoading] = useState(false)
  const { setSession, setGridMeta, setCells, setActivePanel, pushToast } = useStore()
  const { generate } = useGrid()

  // Safe number setter — never stores NaN, falls back to previous value
  const setNum = (key, raw, fallback) => {
    const n = parseFloat(raw)
    setForm(f => ({ ...f, [key]: isNaN(n) ? fallback : n }))
  }

  const rows = Math.floor((form.heightM || 0) / (form.cellSizeM || 1))
  const cols = Math.floor((form.widthM  || 0) / (form.cellSizeM || 1))

  const handleStart = async () => {
    if (!form.projectName.trim()) {
      pushToast('Enter a project name', 'error'); return
    }
    if (!form.widthM || !form.heightM || !form.cellSizeM ||
        form.cellSizeM <= 0 || form.widthM <= 0 || form.heightM <= 0) {
      pushToast('Invalid dimensions — all values must be > 0', 'error'); return
    }
    if (rows < 1 || cols < 1) {
      pushToast('Cell size is too large for these dimensions', 'error'); return
    }

    setLoading(true)
    try {
      // Step 1: create session
      const session = await createSession({
        project_name:  form.projectName.trim(),
        building_name: form.buildingName.trim() || form.projectName.trim(),
        width_m:       form.widthM,
        height_m:      form.heightM,
        cell_size_m:   form.cellSizeM,
      })

      const sid = session.session_id
      setSession(sid, form.projectName.trim())

      // Step 2: generate grid (pass dims explicitly for safety)
      const gridData = await generate(form.widthM, form.heightM, form.cellSizeM)
      if (!gridData) {
        pushToast('Grid creation failed — check backend', 'error')
        setLoading(false)
        return
      }

      setGridMeta({
        grid_rows:   gridData.grid_rows,
        grid_cols:   gridData.grid_cols,
        cell_size_m: form.cellSizeM,
        width_m:     form.widthM,
        height_m:    form.heightM,
      })

      if (gridData.cells) setCells(gridData.cells)

      pushToast(`Grid ready — ${gridData.grid_rows}×${gridData.grid_cols} cells`, 'success')
      setActivePanel('editor')
    } catch (err) {
      console.error('Setup error:', err)
      pushToast('Setup failed: ' + apiErrorMessage(err), 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="project-setup fade-up">
      {/* Logo */}
      <div className="ps-logo">
        <span className="ps-hex">⬡</span>
        <div>
          <h1 className="ps-title">DeadZero</h1>
          <p className="ps-version">v3.0 — Grid-First Floor Plan</p>
        </div>
      </div>

      <p className="ps-desc">
        Build your floor plan on an interactive grid canvas.
        No map upload needed — paint zones, place routers, analyse signal coverage.
      </p>

      <div className="ps-form">
        <div className="field">
          <label>Project Name</label>
          <input
            value={form.projectName}
            onChange={e => setForm(f => ({ ...f, projectName: e.target.value }))}
            placeholder="e.g. Office Block A — Floor 2"
          />
        </div>
        <div className="field">
          <label>Building / Campus</label>
          <input
            value={form.buildingName}
            onChange={e => setForm(f => ({ ...f, buildingName: e.target.value }))}
            placeholder="e.g. Tech Park Block B"
          />
        </div>

        <div className="dim-row">
          <div className="field">
            <label>Floor Width (m)</label>
            <input
              type="number" min={4} max={500}
              value={form.widthM}
              onChange={e => setNum('widthM', e.target.value, form.widthM)}
            />
          </div>
          <div className="field">
            <label>Floor Height (m)</label>
            <input
              type="number" min={4} max={500}
              value={form.heightM}
              onChange={e => setNum('heightM', e.target.value, form.heightM)}
            />
          </div>
          <div className="field">
            <label>Cell Size (m)</label>
            <input
              type="number" min={0.5} max={20} step={0.5}
              value={form.cellSizeM}
              onChange={e => setNum('cellSizeM', e.target.value, form.cellSizeM)}
            />
          </div>
        </div>

        {/* Live preview */}
        <div className="ps-preview">
          <div
            className="ps-preview-grid"
            style={{
              '--cols': Math.min(cols, 20),
              '--rows': Math.min(rows, 12),
            }}
          >
            {Array.from({ length: Math.min(rows, 12) * Math.min(cols, 20) }).map((_, i) => (
              <div key={i} className="ps-cell" />
            ))}
          </div>
          <p className="ps-preview-label">
            {rows} × {cols} = {rows * cols} cells &nbsp;|&nbsp; {form.widthM}m × {form.heightM}m
          </p>
        </div>

        <button
          className="btn btn-primary btn-lg btn-full"
          onClick={handleStart}
          disabled={loading}
        >
          {loading
            ? <><span className="spinner" /> Creating…</>
            : '⬡ Start Floor Plan'}
        </button>
      </div>

      <style>{`
        .project-setup {
          display: flex; flex-direction: column; gap: 20px;
          max-width: 500px; width: 100%; margin: auto;
          padding: 40px 24px; overflow-y: auto; height: 100%;
        }
        .ps-logo { display: flex; align-items: center; gap: 14px; }
        .ps-hex {
          font-size: 40px; color: var(--accent);
          filter: drop-shadow(0 0 14px rgba(99,179,237,0.5));
          animation: float 3s ease-in-out infinite;
        }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
        .ps-title {
          font-family: var(--font-display); font-size: 32px;
          font-weight: 800; color: var(--text-primary); line-height: 1;
          letter-spacing: -0.03em;
        }
        .ps-version { font-size: 10px; color: var(--accent); letter-spacing: 0.06em; margin-top: 3px; }
        .ps-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.7; }
        .ps-form { display: flex; flex-direction: column; gap: 14px; }
        .dim-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
        .ps-preview {
          background: var(--bg-surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: 14px; display: flex; flex-direction: column; gap: 8px;
          align-items: center;
        }
        .ps-preview-grid {
          display: grid;
          grid-template-columns: repeat(var(--cols), 1fr);
          grid-template-rows: repeat(var(--rows), 1fr);
          gap: 1px;
          width: 100%; max-width: 360px;
          aspect-ratio: var(--cols) / var(--rows);
        }
        .ps-cell {
          background: var(--bg-elevated);
          border: 1px solid rgba(99,179,237,0.08);
          border-radius: 1px;
        }
        .ps-preview-label { font-size: 10px; color: var(--accent); }
      `}</style>
    </div>
  )
}