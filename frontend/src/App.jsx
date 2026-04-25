import React from 'react'
import Header from './components/common/Header'
import PocBanner from './components/common/PocBanner'
import DashboardFooter from './components/common/Footer'
import Dashboard from './pages/Dashboard'
import { useDashboard } from './hooks/useDashboard'
import { api } from './utils/api'

export default function App() {
  const { summary, sites, alerts, trend, loading, error, lastRefresh, refresh } = useDashboard(30000)

  const handleTrigger = async () => {
    await api.trigger()
    setTimeout(refresh, 1500)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <PocBanner summary={summary} />
      <Header lastRefresh={lastRefresh} onRefresh={refresh} loading={loading} />

      {/* Error state */}
      {error && (
        <div style={{
          background: 'var(--red-100)', color: 'var(--red-600)',
          padding: '10px 24px', fontSize: 13, fontWeight: 500,
          borderBottom: '1px solid #fca5a5',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          ⚠️ API error: {error} — backend may still be starting up. Retrying…
        </div>
      )}

      {/* Main content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Dashboard
          summary={summary}
          sites={sites}
          alerts={alerts}
          trend={trend}
          loading={loading}
        />
      </main>

      <DashboardFooter summary={summary} lastRefresh={lastRefresh} onTrigger={handleTrigger} />
    </div>
  )
}
