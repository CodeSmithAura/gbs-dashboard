const BASE = '/api/v1/wireless'

async function apiFetch(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
}

export const api = {
  summary:  () => apiFetch(`${BASE}/summary`),
  sites:    () => apiFetch(`${BASE}/sites`),
  alerts:   () => apiFetch(`${BASE}/alerts`),
  trend:    (hours = 168) => apiFetch(`${BASE}/trend?hours=${hours}`),
  health:   () => apiFetch('/health'),
  trigger:  () => fetch(`${BASE}/ingest/trigger`, { method: 'POST' }).then(r => r.json()),
}
