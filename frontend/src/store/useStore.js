import { create } from 'zustand'

/**
 * useStore — Zustand UI state (M3 owns)
 * Stores only UI-level state. All persistent data lives in MongoDB / fetched via API.
 */
const useStore = create((set, get) => ({
  // ── Session / project ────────────────────────────────────────────────────
  sessionId:   null,
  projectName: '',
  gridMeta:    null,   // { grid_rows, grid_cols, cell_size_m, width_m, height_m }
  cells:       [],     // flat array of cell objects from MongoDB grids collection

  setSession:   (id, name) => set({ sessionId: id, projectName: name }),
  setGridMeta:  (meta)     => set({ gridMeta: meta }),
  setCells:     (cells)    => set({ cells }),
  updateCell:   (row, col, patch) =>
    set((s) => ({
      cells: s.cells.map((c) =>
        c.row === row && c.col === col ? { ...c, ...patch } : c
      ),
    })),

  // ── Active panel ─────────────────────────────────────────────────────────
  // 'setup' | 'editor' | 'analysis'
  activePanel: 'setup',
  setActivePanel: (p) => set({ activePanel: p }),

  // ── Painting ─────────────────────────────────────────────────────────────
  activeTool:    'paint',      // 'paint' | 'erase' | 'select'
  activeZone:    'office',
  isPainting:    false,
  setActiveTool: (t) => set({ activeTool: t }),
  setActiveZone: (z) => set({ activeZone: z }),
  setIsPainting: (v) => set({ isPainting: v }),

  // ── Routers ──────────────────────────────────────────────────────────────
  routers: [],
  setRouters:  (r)  => set({ routers: r }),
  addRouter:   (r)  => set((s) => ({ routers: [...s.routers, r] })),
  removeRouter:(id) => set((s) => ({ routers: s.routers.filter((r) => r.router_id !== id) })),

  // ── Analysis results ──────────────────────────────────────────────────────
  signalMatrix:       null,
  qualityMatrix:      null,
  interferenceMatrix: null,
  deadZoneMask:       null,
  deadZoneCount:      0,
  clusters:           [],
  metrics:            null,

  setResults: (data) => set({
    signalMatrix:       data.signal_matrix       ?? null,
    qualityMatrix:      data.quality_matrix      ?? null,
    interferenceMatrix: data.interference_matrix ?? null,
    deadZoneMask:       data.dead_zone_mask       ?? null,
    deadZoneCount:      data.dead_zone_count      ?? 0,
    clusters:           data.clusters            ?? [],
    metrics:            data.metrics             ?? null,
  }),

  // ── Optimisation ──────────────────────────────────────────────────────────
  optimResult: null,
  setOptimResult: (r) => set({ optimResult: r }),

  // ── AI Suggestion ─────────────────────────────────────────────────────────
  suggestion: null,
  setSuggestion:   (s) => set({ suggestion: s }),
  clearSuggestion: ()  => set({ suggestion: null }),

  // ── Overlays ─────────────────────────────────────────────────────────────
  overlays: {
    heatmap:      true,
    deadzone:     true,
    interference: false,
    priority:     false,
    zones:        true,
  },
  overlayOpacity:  0.65,
  toggleOverlay:   (key) => set((s) => ({ overlays: { ...s.overlays, [key]: !s.overlays[key] } })),
  setOpacity:      (v)   => set({ overlayOpacity: v }),

  // ── UI loading / step state ───────────────────────────────────────────────
  isAnalysing:  false,
  isOptimising: false,
  isSuggesting: false,
  analyseSteps: [],
  setAnalysing:    (v) => set({ isAnalysing: v }),
  setOptimising:   (v) => set({ isOptimising: v }),
  setSuggesting:   (v) => set({ isSuggesting: v }),
  setAnalyseSteps: (s) => set({ analyseSteps: s }),

  // ── Router form modal ─────────────────────────────────────────────────────
  routerModal: null,      // null | { row, col } | { ...router, editMode: true }
  openRouterModal:  (d) => set({ routerModal: d }),
  closeRouterModal: ()  => set({ routerModal: null }),

  // ── Cell hover tooltip ────────────────────────────────────────────────────
  hoveredCell: null,
  setHoveredCell: (c) => set({ hoveredCell: c }),

  // ── Toasts ───────────────────────────────────────────────────────────────
  toasts: [],
  pushToast:   (msg, type = 'info') =>
    set((s) => ({ toasts: [...s.toasts, { id: Date.now(), msg, type }] })),
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  // ── Full reset ────────────────────────────────────────────────────────────
  reset: () => set({
    sessionId: null, projectName: '', gridMeta: null, cells: [], routers: [],
    signalMatrix: null, qualityMatrix: null, interferenceMatrix: null,
    deadZoneMask: null, deadZoneCount: 0, clusters: [], metrics: null,
    optimResult: null, suggestion: null, analyseSteps: [],
    isAnalysing: false, isOptimising: false, isSuggesting: false,
    activePanel: 'setup', routerModal: null,
    overlays: { heatmap: true, deadzone: true, interference: false, priority: false, zones: true },
  }),
}))

export default useStore
