import { useCallback } from 'react'
import { createGrid, fetchGrid, saveZones } from '../api/apiClient'
import useStore from '../store/useStore'

export function useGrid() {
  const { sessionId, setGridMeta, setCells, cells, pushToast } = useStore()

  /**
   * generate — creates the NxM cell grid on the backend.
   *
   * IMPORTANT: accepts an explicit `sid` parameter so callers can pass the
   * session_id they just received from POST /api/session WITHOUT waiting for
   * the Zustand store to re-render (which would cause a stale-closure race
   * condition on the first click).
   *
   * Falls back to `sessionId` from the store when `sid` is not supplied
   * (e.g. when called from other components that already have a session).
   */
  const generate = useCallback(async (widthM, heightM, cellSizeM, sid) => {
    const resolvedId = sid ?? sessionId
    if (!resolvedId) {
      pushToast('No session ID — create a session first', 'error')
      return null
    }
    try {
      const data = await createGrid({
        session_id:  resolvedId,
        width_m:     widthM,
        height_m:    heightM,
        cell_size_m: cellSizeM,
      })
      setGridMeta(data)
      return data
    } catch (err) {
      pushToast(
        'Grid creation failed: ' + (err.response?.data?.detail || err.message),
        'error',
      )
      return null
    }
  }, [sessionId, setGridMeta, pushToast])

  const loadGrid = useCallback(async () => {
    if (!sessionId) return null
    try {
      const data = await fetchGrid(sessionId)
      if (data.cells) setCells(data.cells)
      return data
    } catch {
      return null
    }
  }, [sessionId, setCells])

  const persistZones = useCallback(async (updatedCells) => {
    if (!sessionId) return
    try {
      await saveZones({ session_id: sessionId, cells: updatedCells ?? cells })
    } catch (err) {
      pushToast('Zone save failed', 'error')
    }
  }, [sessionId, cells, pushToast])

  return { generate, loadGrid, persistZones }
}