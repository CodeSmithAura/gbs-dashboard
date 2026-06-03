import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../utils/api'

export function useDashboard(baseIntervalMs = 30000) {
  const [data, setData]           = useState({ summary: null, sites: [], alerts: [], trend: [] })
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [lastRefresh, setRefresh] = useState(null)
  const [demoState, setDemoState] = useState(null)
  const intervalRef               = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const [summary, sites, alerts, trend] = await Promise.all([
        api.summary(), api.sites(), api.alerts(), api.trend(),
      ])
      setData({ summary, sites, alerts, trend })
      setError(null)
      setRefresh(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchDemoState = useCallback(async () => {
    try {
      const ds = await api.demoStatus()
      setDemoState(ds)
    } catch {
      // demo endpoint may not be available -- ignore silently
    }
  }, [])

  // Restart the polling interval -- called when demo state changes
  const resetInterval = useCallback((ms) => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => {
      fetchAll()
      fetchDemoState()
    }, ms)
  }, [fetchAll, fetchDemoState])

  useEffect(() => {
    fetchAll()
    fetchDemoState()

    // When demo is running, poll every 3s so UI reflects each snapshot quickly.
    // When idle, fall back to baseIntervalMs (30s).
    const isRunning = demoState?.running
    resetInterval(isRunning ? 3000 : baseIntervalMs)

    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [fetchAll, fetchDemoState, resetInterval, baseIntervalMs, demoState?.running])

  return {
    ...data,
    loading,
    error,
    lastRefresh,
    demoState,
    refresh: fetchAll,
    refreshDemo: fetchDemoState,
  }
}
