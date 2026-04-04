import { useCallback } from 'react'
import { createGrid, fetchGrid, saveZones } from '../api/apiClient'
import useStore from '../store/useStore'

export function useGrid() {
  const { sessionId, setGridMeta, setCells, cells, pushToast } = useStore()

  const generate = useCallback(async (widthM, heightM, cellSizeM) => {
    try {
      const data = await createGrid({ session_id: sessionId, width_m: widthM, height_m: heightM, cell_size_m: cellSizeM })
      setGridMeta(data)
      return data
    } catch (err) {
      pushToast('Grid creation failed: ' + (err.response?.data?.detail || err.message), 'error')
      return null
    }
  }, [sessionId, setGridMeta, pushToast])

  const loadGrid = useCallback(async () => {
    try {
      const data = await fetchGrid(sessionId)
      if (data.cells) setCells(data.cells)
      return data
    } catch { return null }
  }, [sessionId, setCells])

  const persistZones = useCallback(async (updatedCells) => {
    try {
      await saveZones({ session_id: sessionId, cells: updatedCells ?? cells })
    } catch (err) {
      pushToast('Zone save failed', 'error')
    }
  }, [sessionId, cells, pushToast])

  return { generate, loadGrid, persistZones }
}
