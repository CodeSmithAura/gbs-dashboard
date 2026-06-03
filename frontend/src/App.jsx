import React from 'react'
import Header from './components/common/Header'
import PocBanner from './components/common/PocBanner'
import DashboardFooter from './components/common/Footer'
import Dashboard from './pages/Dashboard'
import { useDashboard } from './hooks/useDashboard'
import { api } from './utils/api'

export default function App() {
  const {
    summary, sites, alerts, trend,
    loading, error, lastRefresh,
    demoState,
    refresh, refreshDemo,
  } = useDashboard(30000)

  const handleTrigger = async () => {
    await api.trigger()
    setTimeout(refresh, 1500)
  }

  // After demo start/stop, immediately refresh both data and demo state
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

      {error && (
        <div style={{
          background: 'var(--red-100)', color: 'var(--red-600)',
          padding: '10px 24px', fontSize: 13, fontWeight: 500,
          borderBottom: '1px solid #fca5a5',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          API error: {error} -- retrying...
        </div>
      )}

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Dashboard
          summary={summary}
          sites={sites}
          alerts={alerts}
          trend={trend}
          loading={loading}
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
