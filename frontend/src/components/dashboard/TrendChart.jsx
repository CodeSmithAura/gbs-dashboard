import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'

function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getDate()}/${d.getMonth() + 1} ${String(d.getHours()).padStart(2,'0')}:00`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--slate-900)', color: '#fff',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
      boxShadow: 'var(--shadow-lg)',
    }}>
      <div style={{ marginBottom: 6, color: 'var(--slate-400)', fontSize: 11 }}>{fmt(label)}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, display: 'inline-block' }} />
          <span style={{ color: 'var(--slate-300)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600 }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function TrendChart({ trend }) {
  if (!trend?.length) {
    return (
      <div style={{
        background: 'var(--white)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--slate-200)', padding: 32,
        textAlign: 'center', color: 'var(--slate-400)', fontSize: 13,
      }}>
        Trend data builds up as ingestion cycles run. Check back after a few cycles.
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--white)', borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)', border: '1px solid var(--slate-200)',
      padding: '14px 20px 10px',
    }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 14 }}>
        7-Day Trend — Wireless Health Score & AP Availability
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
          <CartesianGrid stroke="var(--slate-100)" strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" tickFormatter={fmt}
            tick={{ fontSize: 10, fill: 'var(--slate-500)' }} tickLine={false} axisLine={false} />
          <YAxis yAxisId="score" domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--slate-500)' }} tickLine={false} axisLine={false} />
          <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--slate-500)' }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <ReferenceLine yAxisId="score" y={80} stroke="var(--green-600)" strokeDasharray="4 2" strokeOpacity={.4} />
          <ReferenceLine yAxisId="score" y={60} stroke="var(--amber-600)" strokeDasharray="4 2" strokeOpacity={.4} />
          <Line yAxisId="score" type="monotone" dataKey="score" name="Health Score"
            stroke="var(--blue-600)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          <Line yAxisId="pct" type="monotone" dataKey="ap_online_pct" name="AP Online %"
            stroke="var(--green-600)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
