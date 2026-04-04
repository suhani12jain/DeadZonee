import axios from 'axios'

// In dev, use same-origin `/api` so Vite proxies to the backend (see vite.config.js).
// Set VITE_API_URL when the UI is served without that proxy (e.g. production).
const BASE =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '' : 'http://localhost:8000')

const api = axios.create({ baseURL: BASE, timeout: 120_000 })

// ── Session ──────────────────────────────────────────────────────────────────
export const createSession = (body) => api.post('/api/session', body).then(r => r.data)
export const getSession    = (id)  => api.get(`/api/session/${id}`).then(r => r.data)

// ── Grid ─────────────────────────────────────────────────────────────────────
export const createGrid   = (body)       => api.post('/api/grid/create', body).then(r => r.data)
export const saveZones    = (body)       => api.post('/api/grid/save-zones', body).then(r => r.data)
export const fetchGrid    = (sessionId) => api.get(`/api/grid/${sessionId}`).then(r => r.data)

// ── Routers ───────────────────────────────────────────────────────────────────
export const addRouter      = (body)      => api.post('/api/routers', body).then(r => r.data)
export const listRouters    = (sessionId) => api.get(`/api/routers/${sessionId}`).then(r => r.data.routers ?? [])
export const deleteRouter   = (routerId)  => api.delete(`/api/routers/${routerId}`).then(r => r.data)
export const updateRouter   = (id, body)  => api.put(`/api/routers/${id}`, body).then(r => r.data)
export const acceptSuggestion = (body)    => api.post('/api/routers/accept-suggestion', body).then(r => r.data)

// ── Analysis ──────────────────────────────────────────────────────────────────
export const runAnalysis = (sessionId) => api.post('/api/analyse', { session_id: sessionId }).then(r => r.data)
export const getResults  = (sessionId) => api.get(`/api/results/${sessionId}`).then(r => r.data)

// ── Optimise ─────────────────────────────────────────────────────────────────
export const runOptimise    = (sessionId) => api.post('/api/optimise', { session_id: sessionId }).then(r => r.data)
export const getOptimResult = (sessionId) => api.get(`/api/optimise/${sessionId}`).then(r => r.data)

// ── Suggest ───────────────────────────────────────────────────────────────────
export const runSuggest = (sessionId) => api.post('/api/suggest', { session_id: sessionId }).then(r => r.data)

// ── Report ────────────────────────────────────────────────────────────────────
export const downloadReport = async (sessionId) => {
  const res = await api.get('/api/report', { params: { session_id: sessionId }, responseType: 'blob' })
  return res.data
}
export const getReportUrl = (sessionId) => `${BASE}/api/report?session_id=${sessionId}`
