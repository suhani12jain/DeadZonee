import React, { useEffect, useRef, useState } from 'react'
import useStore from './store/useStore'
import { useRouters } from './hooks/useRouters'
import { getResults } from './api/apiClient'

// Panels
import ProjectSetup from './components/Sidebar/ProjectSetup'
import ZoneLabels from './components/Sidebar/ZoneLabels'
import CellInfoPanel from './components/Sidebar/CellInfoPanel'
import GridCanvas from './components/GridEditor/GridCanvas'
import OverlayInsightsPanel from './components/Analysis/OverlayInsightsPanel'
import RouterForm from './components/RouterConfig/RouterForm'
import RouterList from './components/RouterConfig/RouterList'
import MetricsSidebar from './components/Dashboard/MetricsSidebar'
import ZoneSummary from './components/Dashboard/ZoneSummary'
import AnalysisPreview from './components/Analysis/AnalysisPreview'
import OptimizationPanel from './components/Optimization/OptimizationPanel'
import ReportGenerator from './components/Report/ReportGenerator'
import WhatIfPanel from './components/Analysis/WhatIfPanel'

/* ── Toast notification system ──────────────────────────────────────── */
function ToastContainer() {
  const { toasts, dismissToast } = useStore()
  useEffect(() => {
    toasts.forEach(t => {
      const timer = setTimeout(() => dismissToast(t.id), 3800)
      return () => clearTimeout(timer)
    })
  }, [toasts, dismissToast])

  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`} onClick={() => dismissToast(t.id)}>
          <span className="toast-dot" />
          <span className="toast-msg">{t.msg}</span>
        </div>
      ))}
      <style>{`
        .toast-container {
          position: fixed; bottom: 20px; right: 20px;
          display: flex; flex-direction: column; gap: 6px; z-index: 9999;
        }
        .toast {
          display: flex; align-items: center; gap: 8px;
          padding: 9px 14px; border-radius: var(--radius-md);
          background: var(--bg-panel); border: 1px solid var(--border-mid);
          font-size: 11px; cursor: pointer; max-width: 320px;
          animation: slideIn 0.25s var(--ease-snap) both;
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        @keyframes slideIn { from { transform: translateX(110%); opacity: 0; } }
        .toast-success { border-color: rgba(6,214,160,0.35); }
        .toast-error   { border-color: rgba(255,77,109,0.35); }
        .toast-warning { border-color: rgba(255,209,102,0.35); }
        .toast-info    { border-color: var(--border-bright); }
        .toast-dot {
          width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
        }
        .toast-success .toast-dot { background: var(--success); }
        .toast-error   .toast-dot { background: var(--danger); }
        .toast-warning .toast-dot { background: var(--warning); }
        .toast-info    .toast-dot { background: var(--accent); }
        .toast-msg { color: var(--text-primary); }
      `}</style>
    </div>
  )
}

/* ── Sidebar accordion section ───────────────────────────────────────── */
function SideSection({ title, children, defaultOpen = true, accent }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="ss-wrap">
      <button className="ss-header" onClick={() => setOpen(o => !o)} style={{ '--sa': accent }}>
        <span className="ss-title">{title}</span>
        <span className="ss-chevron">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="ss-body">{children}</div>}
      <style>{`
        .ss-wrap { border-bottom: 1px solid var(--border); }
        .ss-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 10px 14px; cursor: pointer; width: 100%;
          background: transparent; border: none;
          transition: background 0.12s;
        }
        .ss-header:hover { background: var(--bg-elevated); }
        .ss-title {
          font-size: 9px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.1em; color: var(--sa, var(--text-muted));
        }
        .ss-chevron { font-size: 10px; color: var(--text-muted); }
        .ss-body { padding: 10px 14px 14px; }
      `}</style>
    </div>
  )
}

/* ── Main App ─────────────────────────────────────────────────────────── */
export default function App() {
  const { activePanel, sessionId, gridMeta, setResults, reset } = useStore()
  const { fetchRouters } = useRouters()
  const canvasContainerRef = useRef()
  const [canvasDims, setCanvasDims] = useState({ w: 800, h: 600 })

  // Measure canvas container on mount + resize
  useEffect(() => {
    const measure = () => {
      if (canvasContainerRef.current) {
        const { width, height } = canvasContainerRef.current.getBoundingClientRect()
        setCanvasDims({ w: Math.max(width, 400), h: Math.max(height, 300) })
      }
    }
    measure()
    const ro = new ResizeObserver(measure)
    if (canvasContainerRef.current) ro.observe(canvasContainerRef.current)
    return () => ro.disconnect()
  }, [])

  // Reload routers when session changes
  useEffect(() => {
    if (sessionId) fetchRouters()
  }, [sessionId])

  useEffect(() => {
    let cancelled = false
    async function hydrateResults() {
      if (!sessionId) return
      try {
        const data = await getResults(sessionId)
        if (!cancelled) setResults(data)
      } catch (err) {
        // Ignore 404 until analysis exists for the current session.
      }
    }
    hydrateResults()
    return () => { cancelled = true }
  }, [sessionId, setResults])

  const isEditor = activePanel !== 'setup'

  return (
    <div className="app-shell">

      {/* ── Top bar ────────────────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-left">
          <span className="tb-hex">⬡</span>
          <span className="tb-title">DeadZero</span>
          <span className="tb-version">v3.0</span>
        </div>
        {isEditor && (
          <div className="topbar-center">
            {useStore.getState().projectName && (
              <span className="tb-project">{useStore.getState().projectName}</span>
            )}
            {gridMeta && (
              <span className="tb-grid badge badge-cyan">
                {gridMeta.grid_rows}×{gridMeta.grid_cols} · {gridMeta.cell_size_m}m cells
              </span>
            )}
          </div>
        )}
        <div className="topbar-right">
          {isEditor && (
            <button className="btn btn-sm btn-danger" onClick={() => {
              if (confirm('Start a new project? Current work will be lost.')) reset()
            }}>
              ✕ New Project
            </button>
          )}
          <span className="tb-hackathon">HackAthon 18 · 18h Sprint</span>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────── */}
      <div className="app-body">

        {/* ── Setup screen ───────────────────────────────────────────── */}
        {!isEditor && (
          <div className="setup-screen">
            <ProjectSetup />
          </div>
        )}

        {/* ── Editor screen ──────────────────────────────────────────── */}
        {isEditor && (
          <>
            {/* Left sidebar — zone painter + cell info */}
            <aside className="sidebar sidebar-left">
              <SideSection title="Zone Painter" accent="var(--accent)" defaultOpen>
                <ZoneLabels />
              </SideSection>
              <SideSection title="Cell Inspector" accent="var(--accent)" defaultOpen>
                <CellInfoPanel />
              </SideSection>
              <SideSection title="Zone Summary" accent="var(--accent-bright)" defaultOpen={false}>
                <ZoneSummary />
              </SideSection>
            </aside>

            {/* Canvas */}
            <main className="canvas-area" ref={canvasContainerRef}>
              <GridCanvas
                containerWidth={canvasDims.w}
                containerHeight={Math.max(canvasDims.h, 260)}
              />
              <OverlayInsightsPanel />
            </main>

            {/* Right sidebar — routers + analysis + optimise + report */}
            <aside className="sidebar sidebar-right">
              <SideSection title="Routers" accent="var(--accent)">
                <RouterList />
              </SideSection>
              <SideSection title="Analysis" accent="var(--success)">
                <AnalysisPreview />
              </SideSection>
              <SideSection title="What-If Agent" accent="var(--accent-bright)" defaultOpen={false}>
                <WhatIfPanel />
              </SideSection>
              <SideSection title="Signal Metrics" accent="var(--sig-good)" defaultOpen={false}>
                <MetricsSidebar />
              </SideSection>
              <SideSection title="Optimise + AI" accent="var(--warning)" defaultOpen={false}>
                <OptimizationPanel />
              </SideSection>
              <SideSection title="Export Report" accent="var(--accent-bright)" defaultOpen={false}>
                <ReportGenerator />
              </SideSection>
            </aside>
          </>
        )}
      </div>

      {/* ── Modals ─────────────────────────────────────────────────────── */}
      <RouterForm />
      <ToastContainer />

      <style>{`
        .app-shell {
          display: flex; flex-direction: column;
          width: 100vw; height: 100vh; overflow: hidden;
        }

        /* Topbar */
        .topbar {
          display: flex; align-items: center; justify-content: space-between;
          height: 44px; padding: 0 16px; flex-shrink: 0;
          background: var(--bg-surface);
          border-bottom: 1px solid var(--border-mid);
        }
        .topbar-left { display: flex; align-items: center; gap: 8px; }
        .tb-hex { font-size: 18px; color: var(--accent); filter: drop-shadow(0 0 6px rgba(99,179,237,0.4)); }
        .tb-title { font-family: var(--font-display); font-size: 16px; font-weight: 800; color: var(--text-primary); letter-spacing: -0.02em; }
        .tb-version { font-size: 9px; color: var(--text-muted); border: 1px solid var(--border); border-radius: 99px; padding: 1px 6px; }
        .topbar-center { display: flex; align-items: center; gap: 10px; }
        .tb-project { font-family: var(--font-display); font-size: 12px; font-weight: 600; color: var(--text-primary); }
        .tb-grid { font-size: 9px; }
        .topbar-right { display: flex; align-items: center; gap: 10px; }
        .tb-hackathon { font-size: 9px; color: var(--text-muted); }

        /* Body */
        .app-body { flex: 1; display: flex; overflow: hidden; }

        /* Setup screen */
        .setup-screen {
          flex: 1; display: flex; align-items: center; justify-content: center;
          overflow-y: auto;
          background-color: var(--bg-base);
          background-image:
            linear-gradient(rgba(99,179,237,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99,179,237,0.03) 1px, transparent 1px);
          background-size: 32px 32px;
        }

        /* Sidebars */
        .sidebar {
          width: 220px; flex-shrink: 0;
          background: var(--bg-surface);
          border-color: var(--border-mid);
          overflow-y: auto; display: flex; flex-direction: column;
        }
        .sidebar-left  { border-right: 1px solid var(--border-mid); }
        .sidebar-right { border-left:  1px solid var(--border-mid); }

        /* Canvas area */
        .canvas-area { flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; }
      `}</style>
    </div>
  )
}
