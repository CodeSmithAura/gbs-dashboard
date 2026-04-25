export const STATUS_COLOR = {
  green:    { bg: 'var(--green-100)', text: 'var(--green-600)', dot: '#16a34a' },
  amber:    { bg: 'var(--amber-100)', text: 'var(--amber-600)', dot: '#d97706' },
  red:      { bg: 'var(--red-100)',   text: 'var(--red-600)',   dot: '#dc2626' },
  none:     { bg: 'var(--slate-100)', text: 'var(--slate-600)', dot: '#94a3b8' },
  info:     { bg: 'var(--blue-50)',   text: 'var(--blue-600)',  dot: '#2563a8' },
  warning:  { bg: 'var(--amber-100)', text: 'var(--amber-600)', dot: '#d97706' },
  critical: { bg: 'var(--red-100)',   text: 'var(--red-600)',   dot: '#dc2626' },
}

export const STATUS_LABEL = {
  green: 'Healthy', amber: 'Degraded', red: 'Critical',
  none: 'Clear', info: 'Info', warning: 'Warning', critical: 'Critical',
}

export function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(iso) {
  if (!iso) return '—'
  return `${fmtDate(iso)}  ${fmtTime(iso)}`
}

export function scoreToStatus(score) {
  if (score >= 80) return 'green'
  if (score >= 60) return 'amber'
  return 'red'
}
