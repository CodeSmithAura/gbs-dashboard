import React from 'react'

export default function KpiCard({ icon, label, value, sub, accent = 'var(--blue-600)', style = {} }) {
  return (
    <div style={{
      background: 'var(--white)',
      borderRadius: 'var(--radius-lg)',
      padding: '18px 20px',
      boxShadow: 'var(--shadow-sm)',
      border: '1px solid var(--slate-200)',
      display: 'flex', alignItems: 'center', gap: 14,
      ...style,
    }}>
      <div style={{
        width: 42, height: 42, borderRadius: 10, flexShrink: 0,
        background: `color-mix(in srgb, ${accent} 12%, transparent)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20,
      }}>
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 11, color: 'var(--slate-500)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.05em' }}>
          {label}
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--slate-900)', lineHeight: 1.2, marginTop: 1 }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: 11, color: 'var(--slate-500)', marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}
