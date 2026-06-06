/**
 * GBS Service Health Dashboard -- API client
 *
 * All calls go through the IIS URL Rewrite proxy (production)
 * or the Vite dev-server proxy (development).
 * Both forward /api/* and /health to the FastAPI backend on port 8000.
 *
 * Error handling:
 *   All functions throw on non-2xx responses with a descriptive message.
 *   Callers (hooks) catch and set error state -- never crashes the UI.
 *
 * Security:
 *   scope parameter is validated server-side before any DB use.
 *   No credentials are held or sent from the frontend.
 */

const LAN  = '/api/v1/lan'
const BASE = '/api/v1/wireless'
const DEMO = '/api/v1/demo'

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${path} -> ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {

  // ------ Wireless pillar ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  summary:  ()            => apiFetch(`${BASE}/summary`),
  sites:    ()            => apiFetch(`${BASE}/sites`),
  alerts:   ()            => apiFetch(`${BASE}/alerts`),
  trend:    (hours = 168) => apiFetch(`${BASE}/trend?hours=${hours}`),
  health:   ()            => apiFetch('/health'),
  trigger:  ()            => apiFetch(`${BASE}/ingest/trigger`, { method: 'POST' }),

  // ------ LAN pillar -- scope-aware ------------------------------------------------------------------------------------------------------------------------------------------
  // scope: 'all' | 'group:<slug>' | 'country:<name>'
  lanSummary:   (scope = 'all')            => apiFetch(`${LAN}/summary?scope=${encodeURIComponent(scope)}`),
  lanSites:     (scope = 'all')            => apiFetch(`${LAN}/sites?scope=${encodeURIComponent(scope)}`),
  lanAlerts:    (scope = 'all')            => apiFetch(`${LAN}/alerts?scope=${encodeURIComponent(scope)}`),
  lanTrend:     (scope = 'all', hours=168) => apiFetch(`${LAN}/trend?scope=${encodeURIComponent(scope)}&hours=${hours}`),
  lanGroups:    ()                         => apiFetch(`${LAN}/groups`),
  lanCountries: ()                         => apiFetch(`${LAN}/countries`),
  lanStatus:    ()                         => apiFetch(`${LAN}/status`),

  // ------ Demo mode ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  demoStart:  (interval) => apiFetch(
    `${DEMO}/start${interval ? `?interval=${interval}` : ''}`,
    { method: 'POST' }
  ),
  demoStop:   () => apiFetch(`${DEMO}/stop`,   { method: 'POST' }),
  demoStatus: () => apiFetch(`${DEMO}/status`),
}
