/**
 * Dashboard -- main page.
 *
 * Renders PillarAccordion passing render functions for each active pillar.
 * The accordion manages expand/collapse state and the overall GBS strip.
 *
 * Option A migration path:
 *   Replace PillarAccordion with PillarCardGrid + DetailDrawer here.
 *   The renderWirelessDetail / renderLanDetail functions are reused unchanged.
 */

import React from 'react'
import PillarAccordion from '../components/dashboard/PillarAccordion'
import ScoreGauge      from '../components/dashboard/ScoreGauge'
import KpiCard         from '../components/dashboard/KpiCard'
import SiteTable       from '../components/dashboard/SiteTable'
import AlertFeed       from '../components/dashboard/AlertFeed'
import TrendChart      from '../components/dashboard/TrendChart'
import LANHealthTile   from '../components/dashboard/LANHealthTile'

const DETAIL_WRAP = {
  padding:      '20px',
  background:   '#f8fafc',
  borderBottom: '1px solid rgba(0,0,0,0.07)',
}

const LABEL = {
  fontSize:      11,
  fontWeight:    700,
  color:         'rgba(0,0,0,0.38)',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  marginBottom:  12,
}

function Spinner() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}
         role="status" aria-label="Loading">
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        border: '3px solid #e2e8f0',
        borderTop: '3px solid #2563eb',
        animation: 'spin 0.8s linear infinite',
      }} />
    </div>
  )
}

export default function Dashboard({
  summary, sites, alerts, trend, loading,
  lanSummary, lanSites, lanAlerts, lanTrend,
  lanScope, lanGroups, lanCountries,
  onLanScopeChange, lanError,
}) {
  if (loading && !summary && !lanSummary) return <Spinner />

  // ------ Wireless detail renderer ------------------------------------------------------------------------------------------------------------------------------------------------
  const renderWirelessDetail = () => (
    <div style={DETAIL_WRAP}>
      {summary ? (
        <>
          <div style={{
            display:             'grid',
            gridTemplateColumns: '160px 1fr',
            gap:                 20,
            marginBottom:        16,
          }}>
            <ScoreGauge score={summary.overall_score} status={summary.status} />
            <div style={{
              display:             'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap:                 10,
              alignContent:        'start',
            }}>
              <KpiCard icon="antenna"      label="APs Online"        value={summary.aps_online}     sub={`of ${summary.total_aps} total`} />
              <KpiCard icon="users"        label="Connected Clients" value={summary.total_clients}  sub="across all sites" />
              <KpiCard icon="bell"         label="Active Alerts"     value={summary.active_alerts}  sub={`${summary.critical_alerts || 0} critical`} />
              <KpiCard icon="circle-check" label="Sites Healthy"     value={summary.sites_healthy}  sub={`${summary.sites_degraded} degraded`} />
              <KpiCard icon="circle-x"     label="Sites Critical"    value={summary.sites_critical} sub="require attention" />
              <KpiCard icon="wifi"         label="Total Sites"       value={summary.total_sites}    sub="monitored" />
            </div>
          </div>

          <div style={{
            display:             'grid',
            gridTemplateColumns: '1fr 1.4fr',
            gap:                 14,
            marginBottom:        14,
          }}>
            <div style={{ border: '1px solid rgba(0,0,0,0.08)', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ ...LABEL, padding: '8px 12px',
                            background: '#fff', borderBottom: '1px solid rgba(0,0,0,0.08)',
                            marginBottom: 0 }}>
                Wireless Alerts
              </div>
              <AlertFeed alerts={alerts} />
            </div>
            <div style={{ border: '1px solid rgba(0,0,0,0.08)', borderRadius: 8, padding: 12 }}>
              <div style={{ ...LABEL, marginBottom: 8 }}>7-Day Trend</div>
              <TrendChart trend={trend} />
            </div>
          </div>

          <SiteTable sites={sites} />
        </>
      ) : (
        <div style={{ color: 'rgba(0,0,0,0.4)', fontSize: 13 }} role="status">
          Wireless data loading...
        </div>
      )}
    </div>
  )

  // ------ LAN detail renderer ---------------------------------------------------------------------------------------------------------------------------------------------------------------
  const renderLanDetail = () => (
    <div style={DETAIL_WRAP}>
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
    </div>
  )

  return (
    <div style={{
      padding:       '20px 24px',
      maxWidth:      1600,
      margin:        '0 auto',
      width:         '100%',
      boxSizing:     'border-box',
    }}>
      <PillarAccordion
        summary={summary}
        sites={sites}
        alerts={alerts}
        trend={trend}
        loading={loading}
        lanSummary={lanSummary}
        lanSites={lanSites}
        lanAlerts={lanAlerts}
        lanTrend={lanTrend}
        lanScope={lanScope}
        lanGroups={lanGroups}
        lanCountries={lanCountries}
        onLanScopeChange={onLanScopeChange}
        lanError={lanError}
        renderWirelessDetail={renderWirelessDetail}
        renderLanDetail={renderLanDetail}
      />
    </div>
  )
}
