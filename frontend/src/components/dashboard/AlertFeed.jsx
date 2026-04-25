import React from 'react'
import { STATUS_COLOR, fmtTime } from '../../utils/helpers'

const SEV_ICON = { critical: '🔴', warning: '🟡', info: 'ℹ️', none: '✅' }

export default function AlertFeed({ alerts }) {
  return (
    <div style={{
      background: 'var(--white)', borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)', border: '1px solid var(--slate-200)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--slate-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>Active Alerts</div>
        <span style={{
          background: alerts.length > 0 ? 'var(--red-100)' : 'var(--green-100)',
          color: alerts.length > 0 ? 'var(--red-600)' : 'var(--green-600)',
          borderRadius: 12, padding: '2px 10px', fontSize: 12, fontWeight: 600,
        }}>
          {alerts.length} active
        </span>
      </div>

      {alerts.length === 0 ? (
        <div style={{ padding: 28, textAlign: 'center', color: 'var(--slate-400)', fontSize: 13 }}>
          ✅ No active alerts — all sites clear
        </div>
      ) : (
        <div style={{ maxHeight: 280, overflowY: 'auto' }}>
          {alerts.map((a, i) => {
            const c = STATUS_COLOR[a.severity] || STATUS_COLOR.none
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '12px 20px',
                borderBottom: i < alerts.length - 1 ? '1px solid var(--slate-100)' : 'none',
                background: i % 2 === 0 ? 'var(--white)' : 'var(--slate-50)',
              }}>
                <div style={{ fontSize: 16, marginTop: 1, flexShrink: 0 }}>
                  {SEV_ICON[a.severity] || '⚠️'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--slate-900)' }}>
                      {a.site_name}
                    </span>
                    <span style={{
                      background: c.bg, color: c.text,
                      borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 600,
                    }}>
                      {a.severity}
                    </span>
                    <span style={{ color: 'var(--slate-400)', fontSize: 11, marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>
                      {fmtTime(a.timestamp)}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--slate-600)', marginTop: 3 }}>
                    {a.description || 'No description'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
