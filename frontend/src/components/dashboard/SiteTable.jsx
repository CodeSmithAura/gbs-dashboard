import React, { useState } from 'react'
import { STATUS_COLOR, STATUS_LABEL } from '../../utils/helpers'

const col = (label, width, key, render) => ({ label, width, key, render })

const COLS = [
  col('Site', '28%', 'site_name', (v) => <strong style={{ color: 'var(--slate-900)' }}>{v}</strong>),
  col('Score', '10%', 'composite_score', (v, row) => {
    const c = STATUS_COLOR[row.status]
    return (
      <span style={{ fontWeight: 700, color: c?.text, fontFamily: 'var(--font-mono)', fontSize: 13 }}>
        {v}
      </span>
    )
  }),
  col('Status', '11%', 'status', (v) => {
    const c = STATUS_COLOR[v] || STATUS_COLOR.none
    return (
      <span style={{
        background: c.bg, color: c.text,
        borderRadius: 12, padding: '2px 9px',
        fontSize: 11, fontWeight: 600,
        display: 'inline-flex', alignItems: 'center', gap: 4,
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.dot, display: 'inline-block' }} />
        {STATUS_LABEL[v] || v}
      </span>
    )
  }),
  col('APs Online', '13%', 'ap_online_pct', (v, row) => (
    <div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{v}%</div>
      <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>{row.ap_online}/{row.ap_total}</div>
    </div>
  )),
  col('Clients', '10%', 'client_count', (v) => (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{v}</span>
  )),
  col('Auth Fails/h', '11%', 'auth_failures_1h', (v) => (
    <span style={{
      fontFamily: 'var(--font-mono)', fontSize: 12,
      color: v > 10 ? 'var(--red-600)' : v > 4 ? 'var(--amber-600)' : 'var(--slate-600)',
      fontWeight: v > 4 ? 600 : 400,
    }}>{v}</span>
  )),
  col('Uplink', '9%', 'uplink_quality', (v) => {
    const colors = { good: 'var(--green-600)', fair: 'var(--amber-600)', poor: 'var(--red-600)', down: 'var(--red-600)' }
    return <span style={{ color: colors[v] || 'var(--slate-600)', fontWeight: 600, fontSize: 12 }}>{v}</span>
  }),
  col('Alert', '8%', 'alert_severity', (v, row) => {
    if (v === 'none') return <span style={{ color: 'var(--slate-400)', fontSize: 11 }}>—</span>
    const c = STATUS_COLOR[v] || STATUS_COLOR.none
    return (
      <span title={row.alert_description} style={{
        background: c.bg, color: c.text,
        borderRadius: 10, padding: '1px 8px',
        fontSize: 11, fontWeight: 600, cursor: 'default',
      }}>
        {v}
      </span>
    )
  }),
]

export default function SiteTable({ sites }) {
  const [sort, setSort] = useState({ key: 'composite_score', dir: -1 })

  const sorted = [...sites].sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key]
    return typeof av === 'number' ? (av - bv) * sort.dir : String(av).localeCompare(String(bv)) * sort.dir
  })

  const toggle = (key) => setSort(s => ({ key, dir: s.key === key ? -s.dir : -1 }))

  return (
    <div style={{
      background: 'var(--white)', borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)', border: '1px solid var(--slate-200)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--slate-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--slate-900)' }}>Site Health — All Sites</div>
        <div style={{ fontSize: 12, color: 'var(--slate-500)' }}>{sites.length} sites</div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--slate-50)' }}>
              {COLS.map(c => (
                <th key={c.key}
                  onClick={() => toggle(c.key)}
                  style={{
                    padding: '9px 14px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600, color: 'var(--slate-600)',
                    textTransform: 'uppercase', letterSpacing: '.04em',
                    cursor: 'pointer', userSelect: 'none', width: c.width,
                    whiteSpace: 'nowrap',
                    borderBottom: '1px solid var(--slate-200)',
                  }}>
                  {c.label}
                  {sort.key === c.key && <span style={{ marginLeft: 4 }}>{sort.dir > 0 ? '↑' : '↓'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((site, i) => (
              <tr key={site.site_id}
                style={{
                  borderBottom: '1px solid var(--slate-100)',
                  background: i % 2 === 0 ? 'var(--white)' : 'var(--slate-50)',
                  transition: 'background .1s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--blue-50)'}
                onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'var(--white)' : 'var(--slate-50)'}
              >
                {COLS.map(c => (
                  <td key={c.key} style={{ padding: '9px 14px', verticalAlign: 'middle' }}>
                    {c.render ? c.render(site[c.key], site) : site[c.key]}
                  </td>
                ))}
              </tr>
            ))}
            {sites.length === 0 && (
              <tr><td colSpan={COLS.length} style={{ padding: 32, textAlign: 'center', color: 'var(--slate-400)' }}>
                No site data available
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
