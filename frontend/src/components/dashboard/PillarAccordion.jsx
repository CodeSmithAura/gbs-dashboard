/**
 * PillarAccordion -- manages the full five-pillar row list.
 *
 * Behaviours:
 *   - Only one pillar expanded at a time
 *   - On mount: auto-expands worst-status pillar (red > amber > first green)
 *   - Clicking expanded row collapses it (toggle)
 *   - Clicking a different row switches expand
 *   - Pending pillars expand to a placeholder card
 *   - Smooth height animation on expand/collapse
 *
 * Option A migration path:
 *   PillarRow -> PillarCard (fixed height card)
 *   Inline detail -> DetailDrawer (slide-in panel)
 *   No changes to the detail content components themselves
 */

import React, { useState, useEffect, useRef } from 'react'
import PillarRow     from './PillarRow'
import ErrorBoundary from '../common/ErrorBoundary'

// ------ Animated expand/collapse container ---------------------------------------------------------------------------------------------------------------------
function AnimatedPanel({ isOpen, id, children }) {
  const ref    = useRef(null)
  const [height, setHeight] = useState(0)

  useEffect(() => {
    if (!ref.current) return
    if (isOpen) {
      setHeight(ref.current.scrollHeight)
    } else {
      setHeight(0)
    }
  }, [isOpen])

  // Recalculate on content change (e.g. scope change reloads LAN data)
  useEffect(() => {
    if (!ref.current || !isOpen) return
    const ro = new ResizeObserver(() => {
      if (ref.current) setHeight(ref.current.scrollHeight)
    })
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [isOpen])

  return (
    <div
      id={id}
      role="region"
      aria-hidden={!isOpen}
      style={{
        height:     isOpen ? height : 0,
        overflow:   'hidden',
        transition: 'height 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      <div ref={ref}>
        {children}
      </div>
    </div>
  )
}

// ------ Pending pillar placeholder ------------------------------------------------------------------------------------------------------------------------------------------------
function PendingDetail({ name, phase, description }) {
  return (
    <div style={{
      padding:    '24px 28px',
      background: '#f8fafc',
      borderBottom: '1px solid rgba(0,0,0,0.07)',
      display:    'flex', gap: 16, alignItems: 'flex-start',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 10,
        background: 'rgba(0,0,0,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, flexShrink: 0,
      }}>
        --
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700,
                      color: 'rgba(0,0,0,0.35)', marginBottom: 4 }}>
          {name}
        </div>
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.4)',
                      marginBottom: 6 }}>
          {phase}
        </div>
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.3)',
                      fontStyle: 'italic' }}>
          {description}
        </div>
      </div>
    </div>
  )
}

// ------ Determine worst status for auto-expand ------------------------------------------------------------------------------------------------------------
function worstPillarId(pillars) {
  const active = pillars.filter(p => p.status)
  const red    = active.find(p => p.status === 'red')
  if (red)    return red.id
  const amber  = active.find(p => p.status === 'amber')
  if (amber)  return amber.id
  if (active.length) return active[0].id
  return null
}

// ------ Main component ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
export default function PillarAccordion({
  // Wireless
  summary, sites, alerts, trend, loading,
  // LAN
  lanSummary, lanSites, lanAlerts, lanTrend,
  lanScope, lanGroups, lanCountries,
  onLanScopeChange, lanError,
  // Children renderers injected by Dashboard
  renderWirelessDetail,
  renderLanDetail,
}) {
  // ------ Build pillar descriptors ------------------------------------------------------------------------------------------------------------------------------------------------
  const pillars = [
    {
      id:     'wireless',
      letter: 'A',
      name:   'Wireless Health',
      source: 'Aruba Central',
      status: summary?.status || null,
      score:  summary?.overall_score,
      kpis: summary ? [
        { label: 'Sites',   value: summary.total_sites },
        { label: 'APs up',  value: summary.aps_online },
        { label: 'Clients', value: summary.total_clients },
      ] : [],
      alertCount:    summary?.active_alerts   || 0,
      criticalCount: summary?.critical_alerts || 0,
    },
    {
      id:     'lan',
      letter: 'E',
      name:   'LAN Health',
      source: 'SolarWinds',
      status: lanSummary?.lan_status || null,
      score:  lanSummary?.overall_score,
      kpis: lanSummary ? [
        { label: 'Nodes',    value: lanSummary.total_nodes },
        { label: 'Down',     value: lanSummary.nodes_down,
          color: lanSummary.nodes_down > 0 ? '#dc2626' : undefined },
        { label: 'Loss',     value: `${lanSummary.avg_loss_pct ?? 0}%` },
      ] : [],
      alertCount:    lanSummary?.active_alerts   || 0,
      criticalCount: lanSummary?.critical_alerts || 0,
    },
    {
      id:      'avd',
      letter:  'B',
      name:    'AVD Services',
      source:  'Azure Monitor',
      status:  null,
      phase:   'Phase 3 -- Azure Monitor integration',
      description: 'Azure Virtual Desktop health monitoring -- coming in Phase 3.',
    },
    {
      id:      'applications',
      letter:  'C',
      name:    'Application Availability',
      source:  'Synthetic probe',
      status:  null,
      phase:   'Phase 4 -- Synthetic URL monitoring',
      description: 'SAP S/4HANA, SAP ECC, and M3 availability -- coming in Phase 4.',
    },
    {
      id:      'printing',
      letter:  'D',
      name:    'Printing Services',
      source:  'Zabbix',
      status:  null,
      phase:   'Phase 5 -- Zabbix integration',
      description: 'Print fleet health via Zabbix JSON-RPC -- coming in Phase 5.',
    },
  ]

  // Auto-expand worst pillar on initial load
  const [expanded, setExpanded] = useState(null)
  const initialised = useRef(false)

  useEffect(() => {
    if (initialised.current) return
    // Wait until at least one pillar has data
    if (!summary && !lanSummary) return
    initialised.current = true
    setExpanded(worstPillarId(pillars))
  }, [summary, lanSummary])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = (id) => {
    setExpanded(prev => prev === id ? null : id)
  }

  // ------ Overall GBS score strip ---------------------------------------------------------------------------------------------------------------------------------------------------
  const activePillars = pillars.filter(p => p.status && typeof p.score === 'number')
  const overallScore  = activePillars.length
    ? activePillars.reduce((sum, p) => sum + p.score, 0) / activePillars.length
    : null

  const overallStatus = activePillars.some(p => p.status === 'red')   ? 'red'
    : activePillars.some(p => p.status === 'amber') ? 'amber'
    : activePillars.length ? 'green' : null

  const statusColor = s =>
    s === 'green' ? '#16a34a' : s === 'amber' ? '#d97706' : s === 'red' ? '#dc2626' : 'rgba(0,0,0,0.3)'

  return (
    <div style={{
      background:   '#ffffff',
      borderRadius: 12,
      border:       '1px solid rgba(0,0,0,0.08)',
      overflow:     'hidden',
    }}>

      {/* ------ GBS overall health strip ------------------------------------------------------------------------------------------------------------------ */}
      <div style={{
        display:        'flex',
        alignItems:     'center',
        gap:            16,
        padding:        '12px 20px',
        background:     '#0f172a',
        borderBottom:   '1px solid rgba(255,255,255,0.06)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 700,
                       color: 'rgba(255,255,255,0.5)',
                       letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          GBS Service Health
        </span>

        {overallScore !== null ? (
          <>
            <span style={{
              fontSize:           24, fontWeight: 800,
              color:              statusColor(overallStatus),
              fontVariantNumeric: 'tabular-nums',
            }}>
              {overallScore.toFixed(1)}
            </span>
            <span style={{
              fontSize:     11, fontWeight: 700,
              color:        statusColor(overallStatus),
              textTransform:'uppercase',
              padding:      '2px 10px',
              background:   'rgba(255,255,255,0.06)',
              borderRadius: 10,
            }}>
              {overallStatus}
            </span>
          </>
        ) : (
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)',
                         fontStyle: 'italic' }}>
            Connecting to data sources...
          </span>
        )}

        <div style={{ flex: 1 }} />

        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>
          {activePillars.length} of {pillars.length} pillars active
        </span>
      </div>

      {/* ------ Pillar rows --------------------------------------------------------------------------------------------------------------------------------------------------------- */}
      {pillars.map(pillar => (
        <div key={pillar.id}>
          <PillarRow
            id={pillar.id}
            letter={pillar.letter}
            name={pillar.name}
            status={pillar.status}
            score={pillar.score}
            kpis={pillar.kpis}
            alertCount={pillar.alertCount}
            criticalCount={pillar.criticalCount}
            phase={pillar.phase}
            source={pillar.source}
            isExpanded={expanded === pillar.id}
            onToggle={() => handleToggle(pillar.id)}
          />

          <AnimatedPanel
            id={`pillar-detail-${pillar.id}`}
            isOpen={expanded === pillar.id}
          >
            <ErrorBoundary pillar={pillar.name}>
              {pillar.id === 'wireless' && renderWirelessDetail()}
              {pillar.id === 'lan'      && renderLanDetail()}
              {!['wireless','lan'].includes(pillar.id) && (
                <PendingDetail
                  name={pillar.name}
                  phase={pillar.phase}
                  description={pillar.description}
                />
              )}
            </ErrorBoundary>
          </AnimatedPanel>
        </div>
      ))}
    </div>
  )
}
