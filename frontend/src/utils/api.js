// All API calls go through the Vite dev-server proxy (vite.config.js).
// The proxy forwards /api/* and /health to http://backend:8000 inside Docker.

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
  // Wireless data
  summary:  ()            => apiFetch(`${BASE}/summary`),
  sites:    ()            => apiFetch(`${BASE}/sites`),
  alerts:   ()            => apiFetch(`${BASE}/alerts`),
  trend:    (hours = 168) => apiFetch(`${BASE}/trend?hours=${hours}`),
  health:   ()            => apiFetch('/health'),
  trigger:  ()            => apiFetch(`${BASE}/ingest/trigger`, { method: 'POST' }),

  // Demo mode
  demoStart:  (interval) => apiFetch(
    `${DEMO}/start${interval ? `?interval=${interval}` : ''}`,
    { method: 'POST' }
  ),
  demoStop:   ()         => apiFetch(`${DEMO}/stop`,   { method: 'POST' }),
  demoStatus: ()         => apiFetch(`${DEMO}/status`),
}
