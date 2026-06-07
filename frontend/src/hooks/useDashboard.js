/**
 * useDashboard -- unified data hook for both pillars.
 *
 * Manages:
 *   - Wireless pillar data (summary, sites, alerts, trend)
 *   - LAN pillar data (lanSummary, lanSites, lanAlerts, lanTrend)
 *   - LAN scope state (selected country / group)
 *   - Combo box options (groups + countries)
 *   - Demo mode state
 *   - Polling interval (3s during demo, 30s otherwise)
 *
 * Design:
 *   - Wireless and LAN fetches run in parallel (Promise.all per pillar)
 *   - LAN scope change triggers immediate re-fetch without waiting for interval
 *   - Combo box options fetched once on mount, refreshed every hour
 *   - Each pillar has its own error state so one failing does not hide the other
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../utils/api'

const COMBO_REFRESH_MS = 60 * 60 * 1000  // refresh groups/countries every hour

export function useDashboard(baseIntervalMs = 30000) {

  // ------ Wireless state ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const [wireless, setWireless] = useState({
    summary: null, sites: [], alerts: [], trend: []
  })
  const [wirelessError, setWirelessError] = useState(null)

  // ------ LAN state ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const [lan, setLan] = useState({
    summary: null, sites: null, alerts: [], trend: []
  })
  const [lanError, setLanError]   = useState(null)
  const [lanScope, setLanScope]   = useState('all')
  const [lanGroups, setLanGroups]     = useState([])
  const [lanCountries, setLanCountries] = useState([])

  // ------ Shared state ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const [loading, setLoading]     = useState(true)
  const [lastRefresh, setRefresh] = useState(null)
  const [demoState, setDemoState] = useState(null)
  const intervalRef               = useRef(null)
  const comboTimerRef             = useRef(null)
  const lanScopeRef               = useRef(lanScope)  // stable ref for interval callbacks

  // Keep scope ref in sync
  useEffect(() => { lanScopeRef.current = lanScope }, [lanScope])

  // ------ Fetch wireless pillar ------------------------------------------------------------------------------------------------------------------------------------------------------
  const fetchWireless = useCallback(async () => {
    try {
      const [summary, sites, alerts, trend] = await Promise.all([
        api.summary(), api.sites(), api.alerts(), api.trend(),
      ])
      setWireless({ summary, sites, alerts, trend })
      setWirelessError(null)
    } catch (e) {
      setWirelessError(e.message)
    }
  }, [])

  // ------ Fetch LAN pillar (scope-aware) ---------------------------------------------------------------------------------------------------------------------------
  const fetchLan = useCallback(async (scope) => {
    const s = scope ?? lanScopeRef.current
    try {
      const [summary, sites, alerts, trend] = await Promise.all([
        api.lanSummary(s),
        api.lanSites(s),
        api.lanAlerts(s),
        api.lanTrend(s),
      ])
      setLan({ summary, sites, alerts, trend })
      setLanError(null)
    } catch (e) {
      setLanError(e.message)
    }
  }, [])

  // ------ Fetch combo box options (groups + countries) ---------------------------------------------------------------------------------
  const fetchComboOptions = useCallback(async () => {
    try {
      const [groups, countries] = await Promise.all([
        api.lanGroups(), api.lanCountries(),
      ])
      setLanGroups(groups   || [])
      setLanCountries(countries || [])
    } catch {
      // Non-critical -- combo box degrades gracefully if this fails
    }
  }, [])

  // ------ Fetch demo state ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const fetchDemoState = useCallback(async () => {
    try {
      const ds = await api.demoStatus()
      setDemoState(ds)
    } catch {
      // Silently ignore -- demo endpoint optional
    }
  }, [])

  // ------ fetchAll -- both pillars in parallel ---------------------------------------------------------------------------------------------------------
  const fetchAll = useCallback(async () => {
    await Promise.all([fetchWireless(), fetchLan(lanScopeRef.current)])
    setRefresh(new Date())
    setLoading(false)
  }, [fetchWireless, fetchLan])

  // ------ Scope change handler -- immediate re-fetch ---------------------------------------------------------------------------------------
  const handleScopeChange = useCallback((newScope) => {
    setLanScope(newScope)
    lanScopeRef.current = newScope
    fetchLan(newScope)
  }, [fetchLan])

  // ------ Polling interval ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const resetInterval = useCallback((ms) => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => {
      fetchAll()
      fetchDemoState()
    }, ms)
  }, [fetchAll, fetchDemoState])

  // ------ Mount and polling setup ------------------------------------------------------------------------------------------------------------------------------------------------
  useEffect(() => {
    fetchAll()
    fetchDemoState()
    fetchComboOptions()

    // Refresh combo box options hourly (countries/groups rarely change)
    comboTimerRef.current = setInterval(fetchComboOptions, COMBO_REFRESH_MS)

    return () => {
      if (intervalRef.current)  clearInterval(intervalRef.current)
      if (comboTimerRef.current) clearInterval(comboTimerRef.current)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // ------ Adjust poll speed when demo runs ------------------------------------------------------------------------------------------------------------------
  useEffect(() => {
    const isRunning = demoState?.running
    resetInterval(isRunning ? 3000 : baseIntervalMs)
  }, [demoState?.running, baseIntervalMs, resetInterval])

  return {
    // Wireless
    summary:       wireless.summary,
    sites:         wireless.sites,
    alerts:        wireless.alerts,
    trend:         wireless.trend,
    wirelessError,

    // LAN
    lanSummary:    lan.summary,
    lanSites:      lan.sites,
    lanAlerts:     lan.alerts,
    lanTrend:      lan.trend,
    lanError,
    lanScope,
    lanGroups,
    lanCountries,
    onLanScopeChange: handleScopeChange,

    // Shared
    loading,
    lastRefresh,
    demoState,
    refresh:      fetchAll,
    refreshDemo:  fetchDemoState,
  }
}
