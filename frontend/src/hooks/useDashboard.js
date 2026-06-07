/**
 * useDashboard -- unified data hook for both pillars.
 *
 * Key design decisions:
 *   - lanScopeRef is the single source of truth for current scope
 *   - ALL fetchLan calls (manual, interval, fetchAll) explicitly pass
 *     lanScopeRef.current -- no implicit fallback that can go stale
 *   - fetchAll passes scope explicitly so the 30s interval always
 *     respects the currently selected country/group
 *   - Scope change is synchronous on the ref before any fetch fires
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../utils/api'

const COMBO_REFRESH_MS = 60 * 60 * 1000

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
  const [lanError, setLanError]         = useState(null)
  const [lanScope, setLanScope]         = useState('all')
  const [lanGroups, setLanGroups]       = useState([])
  const [lanCountries, setLanCountries] = useState([])

  // ------ Shared ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const [loading, setLoading]     = useState(true)
  const [lastRefresh, setRefresh] = useState(null)
  const [demoState, setDemoState] = useState(null)

  // Refs
  const intervalRef   = useRef(null)
  const comboTimerRef = useRef(null)
  // lanScopeRef is the authoritative scope value for all async callbacks.
  // Updated synchronously before any fetch so callbacks always read current value.
  const lanScopeRef = useRef('all')

  // ------ Fetch wireless ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
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

  // ------ Fetch LAN -- always receives scope explicitly, never relies on closure ------
  const fetchLan = useCallback(async (scope) => {
    // scope must always be passed explicitly by the caller.
    // If somehow called without it, read the ref as a safety net.
    const s = (scope !== undefined && scope !== null) ? scope : lanScopeRef.current
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
  }, [])  // stable -- no deps, never recreated

  // ------ Fetch combo options ------------------------------------------------------------------------------------------------------------------------------------------------------------
  const fetchComboOptions = useCallback(async () => {
    try {
      const [groups, countries] = await Promise.all([
        api.lanGroups(), api.lanCountries(),
      ])
      setLanGroups(groups    || [])
      setLanCountries(countries || [])
    } catch {
      // non-critical
    }
  }, [])

  // ------ Fetch demo state ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const fetchDemoState = useCallback(async () => {
    try {
      const ds = await api.demoStatus()
      setDemoState(ds)
    } catch {
      // silently ignore
    }
  }, [])

  // ------ fetchAll -- ALWAYS passes current scope explicitly to fetchLan ---------------------------
  const fetchAll = useCallback(async () => {
    await Promise.all([
      fetchWireless(),
      fetchLan(lanScopeRef.current),  // explicit -- never stale
    ])
    setRefresh(new Date())
    setLoading(false)
  }, [fetchWireless, fetchLan])

  // ------ Scope change -- ref updated first, then fetch ------------------------------------------------------------------------------
  const handleScopeChange = useCallback((newScope) => {
    // Update ref synchronously before fetch so any concurrent interval
    // callback also reads the new scope if it fires during the fetch
    lanScopeRef.current = newScope
    setLanScope(newScope)
    setLan(prev => ({ ...prev, sites: null }))
    fetchLan(newScope)  // explicit scope -- no ambiguity
  }, [fetchLan])

  // ------ Interval management ------------------------------------------------------------------------------------------------------------------------------------------------------------
  const resetInterval = useCallback((ms) => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => {
      // fetchAll reads lanScopeRef.current at call time -- always current
      fetchAll()
      fetchDemoState()
    }, ms)
  }, [fetchAll, fetchDemoState])

  // ------ Mount ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  useEffect(() => {
    fetchAll()
    fetchDemoState()
    fetchComboOptions()
    comboTimerRef.current = setInterval(fetchComboOptions, COMBO_REFRESH_MS)
    return () => {
      if (intervalRef.current)   clearInterval(intervalRef.current)
      if (comboTimerRef.current) clearInterval(comboTimerRef.current)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // ------ Poll speed -- demo vs normal ---------------------------------------------------------------------------------------------------------------------------------
  useEffect(() => {
    resetInterval(demoState?.running ? 3000 : baseIntervalMs)
  }, [demoState?.running, baseIntervalMs, resetInterval])

  return {
    summary:       wireless.summary,
    sites:         wireless.sites,
    alerts:        wireless.alerts,
    trend:         wireless.trend,
    wirelessError,

    lanSummary:       lan.summary,
    lanSites:         lan.sites,
    lanAlerts:        lan.alerts,
    lanTrend:         lan.trend,
    lanError,
    lanScope,
    lanGroups,
    lanCountries,
    onLanScopeChange: handleScopeChange,

    loading,
    lastRefresh,
    demoState,
    refresh:      fetchAll,
    refreshDemo:  fetchDemoState,
  }
}