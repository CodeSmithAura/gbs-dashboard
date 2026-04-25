import React, { useState, useEffect } from 'react'
import { fmtTime } from '../../utils/helpers'

export default function Header({ lastRefresh, onRefresh, loading }) {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header style={{
      height: 'var(--header-h)',
      background: 'var(--blue-900)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      gap: 16,
      boxShadow: '0 2px 8px rgba(0,0,0,.25)',
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      {/* Logo / title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'linear-gradient(135deg,#3b82c4,#60a5d8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, flexShrink: 0,
        }}>📡</div>
        <div>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>
            GBS Health Dashboard
          </div>
          <div style={{ color: 'var(--blue-400)', fontSize: 11, fontWeight: 400 }}>
            Wireless Pillar · POC
          </div>
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {/* Last refresh */}
      <div style={{ color: 'var(--blue-400)', fontSize: 12, textAlign: 'right' }}>
        <div style={{ color: 'var(--slate-400)', fontSize: 11 }}>Last refreshed</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--blue-100)' }}>
          {lastRefresh ? fmtTime(lastRefresh) : '—'}
        </div>
      </div>

      {/* Live clock */}
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 14, color: '#fff',
        background: 'rgba(255,255,255,.08)',
        padding: '4px 12px', borderRadius: 6,
        minWidth: 78, textAlign: 'center',
      }}>
        {fmtTime(now)}
      </div>

      {/* Refresh button */}
      <button
        onClick={onRefresh}
        disabled={loading}
        style={{
          background: loading ? 'rgba(255,255,255,.05)' : 'rgba(255,255,255,.12)',
          border: '1px solid rgba(255,255,255,.2)',
          color: '#fff', borderRadius: 6,
          padding: '6px 14px', fontSize: 12, fontWeight: 500,
          cursor: loading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          transition: 'background .15s',
        }}>
        <span style={{
          display: 'inline-block',
          animation: loading ? 'spin .7s linear infinite' : 'none',
        }}>↻</span>
        Refresh
      </button>
    </header>
  )
}
