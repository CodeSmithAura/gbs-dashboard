/**
 * Dashboard -- main page layout.
 *
 * Layout:
 *   Row 1: Wireless pillar (existing ScoreGauge + KpiCards + SiteTable)
 *   Row 2: LAN Health pillar (new LANHealthTile -- full width)
 *
 * Props are passed straight through from App -- no data fetching here.
 * Adding more pillars in future batches means adding rows to this layout.
 */

import React from 'react'
import ScoreGauge   from '../components/dashboard/ScoreGauge'
import KpiCard      from '../components/dashboard/KpiCard'
import SiteTable    from '../components/dashboard/SiteTable'
import AlertFeed    from '../components/dashboard/AlertFeed'
import TrendChart   from '../components/dashboard/TrendChart'
import LANHealthTile from '../components/dashboard/LANHealthTile'

const SECTION_STYLE = {
  background:   '#ffffff',
  borderRadius: 12,
  border:       '1px solid rgba(0,0,0,0.08)',
  padding:      '16px 20px',
}

const LABEL = {
  fontSize:     11,
  fontWeight:   700,
  color:        'rgba(0,0,0,0.4)',
  letterSpacing:'0.06em',
  textTransform:'uppercase',
  marginBottom: 12,
}

function Spinner() {
  return (
    <div style={{
      flex: 1, display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: 60,
    }}
    role="status" aria-label="Loading dashboard data">
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        border: '3px solid #e2e8f0',
        borderTop: '3px solid #2563eb',
        animation: 'spin 0.8s linear infinite',
      }} />
    </div>
  )
}

export default function Dashboard({
  // Wireless
  summary, sites, alerts, trend, loading,
  // LAN
  lanSummary, lanSites, lanAlerts, lanTrend,
  lanScope, lanGroups, lanCountries,
  onLanScopeChange, lanError,
}) {
  if (loading && !summary && !lanSummary) return <Spinner />

  return (
    <div style={{
      padding:   '20px 24px',
      display:   'flex',
      flexDirection: 'column',
      gap:       20,
      maxWidth:  1600,
      margin:    '0 auto',
      width:     '100%',
      boxSizing: 'border-box',
    }}>

      {/* ------ PILLAR A: Wireless Health ------------------------------------------------------------------------------------------------------------ */}
      <section
        aria-labelledby="wireless-heading"
        style={{ ...SECTION_STYLE }}
      >
        <h2 id="wireless-heading" style={{ ...LABEL, margin: '0 0 12px' }}>
          Pillar A -- Wireless Health (Aruba)
        </h2>

        {summary ? (
          <>
            {/* Row 1a: Score + KPIs */}
            <div style={{
              display:             'grid',
              gridTemplateColumns: '180px 1fr',
              gap:                 20,
              marginBottom:        20,
            }}>
              <ScoreGauge
                score={summary.overall_score}
                status={summary.status}
              />
              <div style={{
                display:             'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap:                 12,
                alignContent:        'start',
              }}>
                <KpiCard
                  icon="antenna"
                  label="APs Online"
                  value={summary.aps_online}
                  sub={`of ${summary.total_aps} total`}
                />
                <KpiCard
                  icon="users"
                  label="Connected Clients"
                  value={summary.total_clients}
                  sub="across all sites"
                />
                <KpiCard
                  icon="bell"
                  label="Active Alerts"
                  value={summary.active_alerts}
                  sub={`${summary.critical_alerts || 0} critical`}
                />
                <KpiCard
                  icon="circle-check"
                  label="Sites Healthy"
                  value={summary.sites_healthy}
                  sub={`${summary.sites_degraded} degraded`}
                />
                <KpiCard
                  icon="circle-x"
                  label="Sites Critical"
                  value={summary.sites_critical}
                  sub="require attention"
                />
                <KpiCard
                  icon="wifi"
                  label="Total Sites"
                  value={summary.total_sites}
                  sub="monitored"
                />
              </div>
            </div>

            {/* Row 1b: Alerts + Trend */}
            <div style={{
              display:             'grid',
              gridTemplateColumns: '1fr 1.4fr',
              gap:                 16,
              marginBottom:        16,
            }}>
              <div style={{
                border:       '1px solid rgba(0,0,0,0.08)',
                borderRadius: 8, overflow: 'hidden',
              }}>
                <div style={{ ...LABEL, padding: '8px 12px',
                              background: '#f8fafc', borderBottom: '1px solid rgba(0,0,0,0.08)',
                              marginBottom: 0 }}>
                  Wireless Alerts
                </div>
                <AlertFeed alerts={alerts} />
              </div>
              <div style={{
                border:       '1px solid rgba(0,0,0,0.08)',
                borderRadius: 8, padding: '12px',
              }}>
                <div style={{ ...LABEL, marginBottom: 8 }}>7-Day Trend</div>
                <TrendChart trend={trend} />
              </div>
            </div>

            {/* Row 1c: Site table */}
            <SiteTable sites={sites} />
          </>
        ) : (
          <div style={{ color: 'rgba(0,0,0,0.4)', fontSize: 13, padding: 16 }}
               role="status">
            Wireless data loading...
          </div>
        )}
      </section>

      {/* ------ PILLAR E: LAN Health --------------------------------------------------------------------------------------------------------------------------- */}
      <LANHealthTile
        lanSummary={lanSummary}
        lanSites={lanSites}
        lanAlerts={lanAlerts}
        lanTrend={lanTrend}
        lanScope={lanScope}
        lanGroups={lanGroups}
        lanCountries={lanCountries}
        onScopeChange={onLanScopeChange}
        lanError={lanError}
        loading={loading}
      />
      </ErrorBoundary>

    </div>
  )
}
