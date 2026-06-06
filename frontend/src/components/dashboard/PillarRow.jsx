/**
 * PillarRow -- compact 56px summary row for one pillar.
 *
 * Renders in two states:
 *   active:  live data -- score, KPIs, alert badge, status dot
 *   pending: no data yet -- greyed placeholder, phase label
 *
 * Accessibility:
 *   role="button" with aria-expanded, aria-controls
 *   Keyboard: Enter / Space toggles expand
 *   Status communicated via colour + text + dot (never colour alone)
 */

import React from 'react'

const C = {
  green:  '#16a34a',
  amber:  '#d97706',
  red:    '#dc2626',
  muted:  'rgba(0,0,0,0.38)',
  border: 'rgba(0,0,0,0.07)',
  bg:     '#ffffff',
  bgHov:  '#f8fafc',
  bgExp:  '#f1f5f9',
}

function statusColor(s) {
  if (s === 'green') return C.green
  if (s === 'amber') return C.amber
  if (s === 'red')   return C.red
  return C.muted
}

function StatusDot({ status }) {
  const color = statusColor(status)
  const pulse = status === 'red'
  return (
    <span
      aria-hidden="true"
      style={{
        width: 9, height: 9, borderRadius: '50%',
        background:  color,
        flexShrink:  0,
        display:     'inline-block',
        animation:   pulse ? 'pulse-dot 1.2s ease-in-out infinite' : 'none',
      }}
    />
  )
}

function KpiChip({ label, value, color }) {
  return (
    <span style={{
      display:    'inline-flex',
      alignItems: 'center',
      gap:        4,
      padding:    '1px 8px',
      background: 'rgba(0,0,0,0.04)',
      borderRadius: 10,
      fontSize:   11,
      color:      color || C.muted,
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'nowrap',
    }}>
      <span style={{ color: C.muted, fontSize: 10 }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{value}</span>
    </span>
  )
}

export default function PillarRow({
  id,
  letter,
  name,
  status,
  score,
  kpis,
  alertCount,
  criticalCount,
  phase,
  isExpanded,
  onToggle,
  source,
}) {
  const isPending = !status
  const rowBg     = isExpanded ? C.bgExp : C.bg

  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onToggle()
    }
  }

  return (
    <div
      id={`pillar-row-${id}`}
      role="button"
      tabIndex={0}
      aria-expanded={isExpanded}
      aria-controls={`pillar-detail-${id}`}
      aria-label={`${name} -- ${isPending ? 'Pending integration' : status + ' ' + score}`}
      onClick={onToggle}
      onKeyDown={handleKey}
      style={{
        display:        'flex',
        alignItems:     'center',
        gap:            14,
        padding:        '0 20px',
        height:         56,
        background:     rowBg,
        borderBottom:   `1px solid ${C.border}`,
        cursor:         'pointer',
        userSelect:     'none',
        transition:     'background 0.12s',
        outline:        'none',
        // Visible focus ring for keyboard navigation
        boxShadow:      undefined,
      }}
      onFocus={e => e.currentTarget.style.boxShadow = '0 0 0 2px #2563eb inset'}
      onBlur={e  => e.currentTarget.style.boxShadow = 'none'}
      onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = C.bgHov }}
      onMouseLeave={e => { e.currentTarget.style.background = rowBg }}
    >
      {/* Letter badge */}
      <span style={{
        width:        22, height: 22,
        borderRadius: 6,
        background:   isPending ? 'rgba(0,0,0,0.06)' : statusColor(status),
        color:        isPending ? C.muted : '#fff',
        fontSize:     11, fontWeight: 800,
        display:      'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink:   0,
        opacity:      isPending ? 0.5 : 1,
      }}>
        {letter}
      </span>

      {/* Status dot */}
      {!isPending && <StatusDot status={status} />}
      {isPending && (
        <span style={{ width: 9, height: 9, borderRadius: '50%',
                       background: 'rgba(0,0,0,0.12)', flexShrink: 0 }} />
      )}

      {/* Pillar name */}
      <span style={{
        fontSize:   13, fontWeight: 600,
        color:      isPending ? C.muted : '#0f172a',
        minWidth:   160, flexShrink: 0,
      }}>
        {name}
      </span>

      {/* Score */}
      {!isPending ? (
        <span style={{
          fontSize:           18, fontWeight: 800,
          color:              statusColor(status),
          minWidth:           52, flexShrink: 0,
          fontVariantNumeric: 'tabular-nums',
        }}>
          {typeof score === 'number' ? score.toFixed(1) : '--'}
        </span>
      ) : (
        <span style={{ fontSize: 11, color: C.muted, fontStyle: 'italic',
                       flexShrink: 0 }}>
          {phase || 'Pending integration'}
        </span>
      )}

      {/* KPI chips */}
      {!isPending && (
        <div style={{ display: 'flex', gap: 6, flex: 1, flexWrap: 'nowrap',
                      overflow: 'hidden' }}>
          {(kpis || []).map((k, i) => (
            <KpiChip key={i} label={k.label} value={k.value} color={k.color} />
          ))}
        </div>
      )}

      {isPending && <div style={{ flex: 1 }} />}

      {/* Alert badge */}
      {!isPending && alertCount > 0 && (
        <span style={{
          padding:      '2px 8px',
          background:   criticalCount > 0 ? '#fef2f2' : '#fffbeb',
          color:        criticalCount > 0 ? C.red : C.amber,
          border:       `1px solid ${criticalCount > 0 ? '#fca5a5' : '#fcd34d'}`,
          borderRadius: 10,
          fontSize:     11, fontWeight: 700,
          flexShrink:   0,
          whiteSpace:   'nowrap',
        }}
        aria-label={`${alertCount} alerts, ${criticalCount} critical`}>
          {criticalCount > 0 ? `${criticalCount} critical` : `${alertCount} alerts`}
        </span>
      )}

      {/* Source label */}
      {!isPending && source && (
        <span style={{ fontSize: 10, color: C.muted,
                       flexShrink: 0, whiteSpace: 'nowrap' }}>
          {source}
        </span>
      )}

      {/* Chevron */}
      <svg
        width="14" height="14" viewBox="0 0 14 14"
        fill="none" aria-hidden="true"
        style={{
          flexShrink:  0,
          marginLeft:  4,
          transition:  'transform 0.2s',
          transform:   isExpanded ? 'rotate(180deg)' : 'none',
          color:       C.muted,
        }}
      >
        <path d="M3 5L7 9L11 5"
              stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      </svg>
    </div>
  )
}
