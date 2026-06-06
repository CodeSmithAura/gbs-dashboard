/**
 * App -- root component.
 * Wires useDashboard hook to all pillar components.
 * Passes LAN scope and demo state down to relevant components.
 */
import React from 'react'
import Header        from './components/common/Header'
import PocBanner     from './components/common/PocBanner'
import DashboardFooter from './components/common/Footer'
import Dashboard     from './pages/Dashboard'
import { useDashboard } from './hooks/useDashboard'
import { api } from './utils/api'

export default function App() {
  const {
    summary, sites, alerts, trend,
    wirelessError,
    lanSummary, lanSites, lanAlerts, lanTrend,
    lanScope, lanGroups, lanCountries,
    onLanScopeChange,
    lanError,
    loading, lastRefresh,
    demoState,
    refresh, refreshDemo,
  } = useDashboard(30000)

  const handleTrigger = async () => {
    await api.trigger()
    setTimeout(refresh, 1500)
  }

  const handleDemoChange = () => {
    setTimeout(() => { refresh(); refreshDemo() }, 800)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

      <PocBanner
        summary={summary}
        demoState={demoState}
        onDemoChange={handleDemoChange}
      />

      <Header lastRefresh={lastRefresh} onRefresh={refresh} loading={loading} />

      {(wirelessError) && (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            background: '#fef2f2', color: '#dc2626',
            padding: '10px 24px', fontSize: 13, fontWeight: 500,
            borderBottom: '1px solid #fca5a5',
            display: 'flex', alignItems: 'center', gap: 8,
          }}
        >
          Wireless API error: {wirelessError} -- retrying...
        </div>
      )}

      <main
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto' }}
        id="main-content"
      >
        <Dashboard
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
        />
      </main>

      <DashboardFooter
        summary={summary}
        lastRefresh={lastRefresh}
        onTrigger={handleTrigger}
      />
    </div>
  )
}
