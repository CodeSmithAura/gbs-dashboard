import React from 'react'
import { STATUS_COLOR, STATUS_LABEL } from '../../utils/helpers'

export default function ScoreGauge({ score, status, label, size = 140 }) {
  const c = STATUS_COLOR[status] || STATUS_COLOR.none
  const r = (size / 2) - 10
  const circ = 2 * Math.PI * r
  const filled = (score / 100) * circ
  const cx = size / 2
  const cy = size / 2

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          {/* Track */}
          <circle cx={cx} cy={cy} r={r}
            fill="none" stroke="var(--slate-200)" strokeWidth={10} />
          {/* Progress */}
          <circle cx={cx} cy={cy} r={r}
            fill="none" stroke={c.dot} strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ}`}
            style={{ transition: 'stroke-dasharray .6s ease' }}
          />
        </svg>
        {/* Score text */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: size * .22, fontWeight: 700, color: c.text, lineHeight: 1 }}>
            {Math.round(score)}
          </span>
          <span style={{ fontSize: size * .09, color: 'var(--slate-500)', marginTop: 2 }}>/ 100</span>
        </div>
      </div>

      {/* Status badge */}
      <div style={{
        background: c.bg, color: c.text,
        borderRadius: 20, padding: '3px 12px',
        fontSize: 12, fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%',
          background: c.dot, display: 'inline-block',
          animation: status === 'red' ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
        }} />
        {STATUS_LABEL[status] || status}
      </div>

      {label && <div style={{ fontSize: 12, color: 'var(--slate-600)', fontWeight: 500 }}>{label}</div>}
    </div>
  )
}
