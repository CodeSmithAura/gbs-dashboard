import { useState, useEffect, useCallback } from 'react'
import { api } from '../utils/api'

export function useDashboard(intervalMs = 30000) {
  const [data, setData]       = useState({ summary: null, sites: [], alerts: [], trend: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [summary, sites, alerts, trend] = await Promise.all([
        api.summary(), api.sites(), api.alerts(), api.trend(),
      ])
      setData({ summary, sites, alerts, trend })
      setError(null)
      setLastRefresh(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, intervalMs)
    return () => clearInterval(id)
  }, [fetchAll, intervalMs])

  return { ...data, loading, error, lastRefresh, refresh: fetchAll }
}
