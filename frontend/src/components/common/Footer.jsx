import React from 'react'
import { fmtDateTime } from '../../utils/helpers'

export default function DashboardFooter({ summary, lastRefresh, onTrigger }) {
  return (
    <footer style={{
      background: 'var(--slate-800)',
      color: 'var(--slate-400)',
      padding: '10px 24px',
      display: 'flex', alignItems: 'center', gap: 20,
      fontSize: 11, fontFamily: 'var(--font-mono)',
      flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: summary ? 'var(--green-600)' : 'var(--slate-600)',
          display: 'inline-block',
        }} />
        <span style={{ color: 'var(--slate-300)' }}>
          Source: {summary?.data_source_type?.toUpperCase() || '—'}
        </span>
      </div>

      <div>
        File: <span style={{ color: 'var(--slate-300)' }}>
          {summary?.data_source_path?.split('/').pop() || '—'}
        </span>
      </div>

      <div>
        Last ingest: <span style={{ color: 'var(--slate-300)' }}>
          {fmtDateTime(summary?.last_ingested_at)}
        </span>
      </div>

      <div>
        Dashboard refresh: <span style={{ color: 'var(--slate-300)' }}>
          {fmtDateTime(lastRefresh)}
        </span>
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={onTrigger} style={{
          background: 'rgba(255,255,255,.07)',
          border: '1px solid rgba(255,255,255,.12)',
          color: 'var(--slate-300)', borderRadius: 4,
          padding: '3px 10px', fontSize: 11, cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
        }}>
          ⚡ Trigger Ingest
        </button>
        <span style={{ color: 'var(--slate-600)' }}>GBS-SOW-ARUBA-POC-v1.0</span>
      </div>
    </footer>
  )
}
