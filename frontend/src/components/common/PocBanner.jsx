import React from 'react'

export default function PocBanner({ summary }) {
  if (!summary) return null

  const src  = summary.data_source_type === 'file' ? 'File' : 'Live API'
  const path = summary.data_source_path?.split('/').pop() || '—'
  const isFile = summary.data_source_type === 'file'

  return (
    <div style={{
      background: isFile ? '#7c3aed' : 'var(--green-600)',
      color: '#fff',
      padding: '8px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      fontSize: 12,
      fontWeight: 500,
      letterSpacing: '.02em',
    }}>
      {/* Pulsing dot */}
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: isFile ? '#c4b5fd' : '#86efac',
        display: 'inline-block',
        animation: 'pulse-dot 2s ease-in-out infinite',
        flexShrink: 0,
      }} />

      {isFile
        ? <>
            <strong>POC MODE</strong>
            <span style={{ opacity: .85 }}>·  Data source: file  ·  File: {path}  ·  Live API available in Phase 2</span>
          </>
        : <>
            <strong>LIVE MODE</strong>
            <span style={{ opacity: .85 }}>·  Data source: HPE Aruba Central API</span>
          </>
      }

      <span style={{ marginLeft: 'auto', opacity: .7, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        {src.toUpperCase()} · GBS-SOW-ARUBA-POC-v1.0
      </span>
    </div>
  )
}
