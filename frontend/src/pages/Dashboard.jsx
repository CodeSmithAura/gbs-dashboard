import React from 'react'
import ScoreGauge from '../components/dashboard/ScoreGauge'
import KpiCard from '../components/dashboard/KpiCard'
import SiteTable from '../components/dashboard/SiteTable'
import AlertFeed from '../components/dashboard/AlertFeed'
import TrendChart from '../components/dashboard/TrendChart'
import { api } from '../utils/api'

export default function Dashboard({ summary, sites, alerts, trend, loading }) {
  const s = summary

  if (loading && !s) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 14 }}>
        <div style={{ width: 36, height: 36, border: '3px solid var(--blue-200)', borderTopColor: 'var(--blue-600)', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
        <div style={{ color: 'var(--slate-500)', fontSize: 14 }}>Loading dashboard data…</div>
      </div>
    )
  }

  const handleTrigger = async () => {
    await api.trigger()
    window.location.reload()
  }

  return (
    <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20, flex: 1 }}
      className="animate-fade-in">

      {/* ── Row 1: Gauge + KPI cards ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 20 }}>
        {/* Gauge */}
        <div style={{
          background: 'var(--white)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-sm)', border: '1px solid var(--slate-200)',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', padding: '20px 16px', gap: 8,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--slate-500)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>
            Wireless Health
          </div>
          <ScoreGauge
            score={s?.overall_score ?? 0}
            status={s?.status ?? 'red'}
            size={130}
          />
        </div>

        {/* KPI grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          <KpiCard icon="📡" label="Total Sites" value={s?.total_sites ?? '—'}
            sub={`${s?.sites_healthy ?? 0} healthy · ${s?.sites_degraded ?? 0} degraded · ${s?.sites_critical ?? 0} critical`} />
          <KpiCard icon="🔵" label="Access Points" value={s?.aps_online ?? '—'}
            sub={`of ${s?.total_aps ?? '—'} total · ${s?.ap_online_pct ?? '—'}% online`}
            accent="var(--blue-600)" />
          <KpiCard icon="👥" label="Clients Connected" value={s?.total_clients?.toLocaleString() ?? '—'}
            sub="across all sites" accent="var(--green-600)" />
          <KpiCard icon="🔔" label="Active Alerts" value={s?.active_alerts ?? 0}
            sub={`${s?.critical_alerts ?? 0} critical`}
            accent={s?.active_alerts > 0 ? 'var(--red-600)' : 'var(--green-600)'}
            style={{ borderLeft: s?.active_alerts > 0 ? '3px solid var(--red-600)' : '3px solid var(--green-600)' }} />
          <KpiCard icon="✅" label="Healthy Sites" value={s?.sites_healthy ?? 0}
            sub={`${s?.sites_critical ?? 0} sites need attention`}
            accent="var(--green-600)" />
          <KpiCard icon="📶" label="Uplink Quality"
            value={sites.filter(s => s.uplink_quality === 'good').length}
            sub={`of ${sites.length} sites on good uplink`}
            accent="var(--blue-500)" />
        </div>
      </div>

      {/* ── Row 2: Alerts + Trend ──────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <AlertFeed alerts={alerts} />
        <TrendChart trend={trend} />
      </div>

      {/* ── Row 3: Site table ──────────────────────────────────────── */}
      <SiteTable sites={sites} />
    </div>
  )
}
