import { useCallback } from 'react'
import { runAnalysis, getResults, runOptimise, runSuggest, acceptSuggestion, listRouters } from '../api/apiClient'
import useStore from '../store/useStore'

export function useAnalysis() {
  const {
    sessionId,
    setAnalysing, setAnalyseSteps, setResults,
    setOptimising, setOptimResult,
    setSuggesting, setSuggestion, clearSuggestion,
    setRouters, pushToast,
  } = useStore()

  const analyse = useCallback(async () => {
    if (!sessionId) return
    setAnalysing(true)
    setAnalyseSteps([])
    try {
      const res = await runAnalysis(sessionId)
      setAnalyseSteps(res.steps ?? [])
      const data = await getResults(sessionId)
      setResults(data)
      const anyErr = (res.steps ?? []).some(s => s.status === 'error')
      pushToast(anyErr ? 'Analysis done with errors' : 'Analysis complete ✓', anyErr ? 'warning' : 'success')
    } catch (err) {
      pushToast('Analysis failed: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setAnalysing(false)
    }
  }, [sessionId, setAnalysing, setAnalyseSteps, setResults, pushToast])

  const optimise = useCallback(async () => {
    if (!sessionId) return
    setOptimising(true)
    try {
      const res = await runOptimise(sessionId)
      setOptimResult(res)
      pushToast(`Optimised! +${res.improvement_pct?.toFixed(1)}% via ${res.algorithm}`, 'success')
    } catch (err) {
      pushToast('Optimisation failed: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setOptimising(false)
    }
  }, [sessionId, setOptimising, setOptimResult, pushToast])

  const suggest = useCallback(async () => {
    if (!sessionId) return
    setSuggesting(true)
    try {
      const res = await runSuggest(sessionId)
      setSuggestion(res)
      pushToast('AI suggestion ready', 'info')
    } catch (err) {
      pushToast('Suggestion failed: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setSuggesting(false)
    }
  }, [sessionId, setSuggesting, setSuggestion, pushToast])

  const acceptAndReanalyse = useCallback(async (suggestionId) => {
    if (!sessionId) return
    try {
      await acceptSuggestion({ session_id: sessionId, suggestion_id: suggestionId })
      clearSuggestion()
      const routers = await listRouters(sessionId)
      setRouters(routers)
      pushToast('Router placed — re-analysing…', 'info')
      await analyse()
    } catch (err) {
      pushToast('Accept failed', 'error')
    }
  }, [sessionId, clearSuggestion, setRouters, analyse, pushToast])

  return { analyse, optimise, suggest, acceptAndReanalyse }
}
