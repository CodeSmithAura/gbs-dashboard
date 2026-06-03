import React, { useState } from 'react'
import { api } from '../../utils/api'

//  Scenario label lookup (matches snapshot filenames) 
const SCENARIO_LABELS = {
  'snapshot_01_normal.csv':            { label: 'All Sites Healthy',          color: '#16a34a' },
  'snapshot_02_normal_peak.csv':       { label: 'Peak Business Hours',        color: '#16a34a' },
  'snapshot_03_branch_warning.csv':    { label: 'Branch Warning',             color: '#d97706' },
  'snapshot_04_branch_degraded.csv':   { label: 'Branch Degraded',            color: '#d97706' },
  'snapshot_05_outage_spreading.csv':  { label: 'Outage Spreading',           color: '#dc2626' },
  'snapshot_06_major_outage.csv':      { label: 'Major Outage',               color: '#dc2626' },
  'snapshot_07_dc_impact.csv':         { label: 'Data Centre Impact',         color: '#dc2626' },
  'snapshot_08_partial_recovery.csv':  { label: 'Partial Recovery',           color: '#d97706' },
  'snapshot_09_recovering.csv':        { label: 'Recovering',                 color: '#d97706' },
  'snapshot_10_recovered.csv':         { label: 'Fully Recovered',            color: '#16a34a' },
}

const DEFAULT_INTERVALS = [
  { label: '10s', value: 10  },
  { label: '30s', value: 30  },
  { label: '60s', value: 60  },
  { label: '2m',  value: 120 },
]

export default function PocBanner({ summary, demoState, onDemoChange }) {
  const [interval, setInterval_]  = useState(30)
  const [busy, setBusy]           = useState(false)
  const [err,  setErr]            = useState(null)

  if (!summary) return null

  const isFile    = summary.data_source_type === 'file'
  const isRunning = demoState?.running === true
  const fileName  = summary.data_source_path?.split('/').pop() || ''

  //  Current snapshot info 
  const currentFile = demoState?.current_file || ''
  const scenario    = SCENARIO_LABELS[currentFile] || null
  const stepNum     = demoState?.current_index    ?? 0
  const stepTotal   = demoState?.total_snapshots  ?? 0
  const stepDisplay = stepTotal > 0
    ? `${((stepNum - 1 + stepTotal) % stepTotal) + 1} / ${stepTotal}`
    : null

  //  Handlers 
  async function handleStart() {
    setBusy(true); setErr(null)
    try {
      const res = await api.demoStart(interval)
      if (!res.ok) setErr(res.error || 'Could not start demo')
      else if (onDemoChange) onDemoChange()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  async function handleStop() {
    setBusy(true); setErr(null)
    try {
      await api.demoStop()
      if (onDemoChange) onDemoChange()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  //  Styles 
  const bannerBg = isRunning ? '#1e1b4b' : isFile ? '#5b21b6' : '#166534'

  const pill = (bg, text, children) => (
    <span style={{
      background: bg, color: text,
      borderRadius: 20, padding: '2px 10px',
      fontSize: 11, fontWeight: 600,
      display: 'inline-flex', alignItems: 'center', gap: 5,
    }}>
      {children}
    </span>
  )

  const dot = (color, pulse = false) => (
    <span style={{
      width: 7, height: 7, borderRadius: '50%',
      background: color, display: 'inline-block', flexShrink: 0,
      animation: pulse ? 'pulse-dot 1.2s ease-in-out infinite' : 'none',
    }} />
  )

  const btn = (label, onClick, disabled, accent) => (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      style={{
        background: disabled || busy ? 'rgba(255,255,255,.08)' : accent,
        border: `1px solid ${disabled || busy ? 'rgba(255,255,255,.15)' : accent}`,
        color: disabled || busy ? 'rgba(255,255,255,.4)' : '#fff',
        borderRadius: 6, padding: '4px 14px',
        fontSize: 12, fontWeight: 600,
        cursor: disabled || busy ? 'not-allowed' : 'pointer',
        transition: 'all .15s', whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{
      background: bannerBg,
      color: '#fff',
      padding: '0 20px',
      fontSize: 12,
      fontFamily: 'var(--font-sans)',
      borderBottom: '1px solid rgba(255,255,255,.08)',
    }}>

      {/*  Main row  */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 44, flexWrap: 'wrap' }}>

        {/* Mode badge */}
        {isRunning
          ? pill('rgba(239,68,68,.25)', '#fca5a5', <>{dot('#ef4444', true)} DEMO RUNNING</>)
          : pill('rgba(255,255,255,.12)', 'rgba(255,255,255,.8)', <>{dot('#c4b5fd')} POC MODE</>)
        }

        {/* Current state info */}
        {isRunning && scenario && (
          <>
            <span style={{ color: 'rgba(255,255,255,.5)' }}>|</span>
            <span style={{ color: 'rgba(255,255,255,.7)' }}>Step {stepDisplay}</span>
            <span style={{ color: 'rgba(255,255,255,.5)' }}>--</span>
            <span style={{
              color: scenario.color,
              fontWeight: 600,
            }}>
              {scenario.label}
            </span>
          </>
        )}

        {!isRunning && (
          <span style={{ color: 'rgba(255,255,255,.55)' }}>
            Source: file &nbsp;&nbsp; {fileName}
          </span>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Interval selector */}
        {!isRunning && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'rgba(255,255,255,.5)', fontSize: 11 }}>Interval:</span>
            {DEFAULT_INTERVALS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setInterval_(opt.value)}
                style={{
                  background: interval === opt.value ? 'rgba(255,255,255,.25)' : 'rgba(255,255,255,.06)',
                  border: `1px solid ${interval === opt.value ? 'rgba(255,255,255,.4)' : 'rgba(255,255,255,.12)'}`,
                  color: interval === opt.value ? '#fff' : 'rgba(255,255,255,.55)',
                  borderRadius: 4, padding: '2px 9px',
                  fontSize: 11, fontWeight: interval === opt.value ? 700 : 400,
                  cursor: 'pointer',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* Demo running info */}
        {isRunning && (
          <span style={{ color: 'rgba(255,255,255,.45)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            {demoState.interval_seconds}s interval
          </span>
        )}

        {/* Action buttons */}
        {isRunning
          ? btn('  Stop Demo', handleStop, false, '#dc2626')
          : btn('  Run Demo', handleStart, false, '#4f46e5')
        }

        {/* Ref tag */}
        <span style={{ color: 'rgba(255,255,255,.3)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
          GBS-SOW-ARUBA-POC-v1.0
        </span>
      </div>

      {/*  Progress bar (demo running only)  */}
      {isRunning && stepTotal > 0 && (
        <div style={{ paddingBottom: 6 }}>
          <div style={{
            display: 'flex', gap: 3,
          }}>
            {Array.from({ length: stepTotal }).map((_, i) => {
              const done = i < ((stepNum - 1 + stepTotal) % stepTotal)
              const curr = i === ((stepNum - 1 + stepTotal) % stepTotal)
              return (
                <div key={i} style={{
                  flex: 1, height: 3, borderRadius: 2,
                  background: curr ? '#818cf8'
                    : done ? 'rgba(255,255,255,.35)'
                    : 'rgba(255,255,255,.1)',
                  transition: 'background .3s',
                }} />
              )
            })}
          </div>
        </div>
      )}

      {/*  Error message  */}
      {err && (
        <div style={{
          background: 'rgba(239,68,68,.15)',
          borderRadius: 4, padding: '5px 12px',
          fontSize: 11, color: '#fca5a5',
          marginBottom: 6,
        }}>
          {err}
        </div>
      )}
    </div>
  )
}
