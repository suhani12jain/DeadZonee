import { useCallback } from 'react'
import { addRouter, listRouters, deleteRouter, updateRouter } from '../api/apiClient'
import useStore from '../store/useStore'

export function useRouters() {
  const {
    sessionId,
    setRouters,
    addRouter:  addToStore,
    removeRouter,
    pushToast,
  } = useStore()

  // ── Fetch all routers for session ─────────────────────────────────────────
  const fetchRouters = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await listRouters(sessionId)
      // API returns { routers: [...], count: N }
      const list = Array.isArray(data) ? data : (data.routers ?? [])
      setRouters(list)
    } catch (err) {
      console.error('fetchRouters failed:', err)
    }
  }, [sessionId, setRouters])

  // ── Add a new router ──────────────────────────────────────────────────────
  const createRouter = useCallback(async (formData) => {
    if (!sessionId) return null
    try {
      const doc = await addRouter({ ...formData, session_id: sessionId })
      addToStore(doc)
      pushToast(`Router "${formData.name}" placed`, 'success')
      return doc
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      pushToast('Failed to add router: ' + detail, 'error')
      return null
    }
  }, [sessionId, addToStore, pushToast])

  // ── Delete a router ───────────────────────────────────────────────────────
  const removeRouterById = useCallback(async (routerId, name) => {
    try {
      await deleteRouter(routerId)
      removeRouter(routerId)
      pushToast(`Router "${name}" removed`, 'info')
    } catch (err) {
      pushToast('Failed to remove router', 'error')
    }
  }, [removeRouter, pushToast])

  // ── Edit a router ─────────────────────────────────────────────────────────
  const editRouter = useCallback(async (routerId, updates) => {
    try {
      const doc = await updateRouter(routerId, updates)
      // Refresh full list to stay in sync
      await fetchRouters()
      pushToast('Router updated', 'success')
      return doc
    } catch (err) {
      pushToast('Failed to update router', 'error')
      return null
    }
  }, [fetchRouters, pushToast])

  return { fetchRouters, createRouter, removeRouterById, editRouter }
}