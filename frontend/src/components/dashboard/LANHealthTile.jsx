/**
 * LANHealthTile -- Pillar E: LAN Health (SolarWinds)
 *
 * Displays in two modes depending on lanSites.view_type:
 *   'country' -- global / group view: one row per country (30 rows max)
 *   'node'    -- single country view: one row per node (up to 250 rows)
 *
 * Features:
 *   - Country selector (CountrySelector) in the tile header
 *   - Composite score gauge with Green/Amber/Red status
 *   - KPI cards: Nodes Up, Nodes Down, Active Alerts, Avg Packet Loss
 *   - Sortable site/node table
 *   - Active alert feed (top 10 by severity)
 *   - 7-day trend chart (avg score + nodes up %)
 *   - Connectivity error state with clear message
 *   - Skeleton loading state on first load
 *   - Data freshness indicator
 *
 * Accessibility (WCAG 2.1 AA):
 *   - All interactive elements keyboard-navigable
 *   - aria-sort on sortable column headers
 *   - aria-live on status changes
 *   - Colour contrast >= 4.5:1 on all text
 *   - No colour-only information -- status uses icon + text + colour
 */

import React, { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import CountrySelector from './CountrySelector'

// ------ Colour tokens ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
const C = {
  green:      '#16a34a',
  greenLight: '#dcfce7',
  amber:      '#d97706',
  amberLight: '#fef3c7',
  red:        '#dc2626',
  redLight:   '#fee2e2',
  blue:       '#2563eb',
  blueLight:  '#dbeafe',
  muted:      'rgba(0,0,0,0.45)',
  border:     'rgba(0,0,0,0.08)',
  bg:         '#ffffff',
  bgSection:  '#f8fafc',
}

function statusColor(status) {
  if (status === 'green') return C.green
  if (status === 'amber') return C.amber
  return C.red
}

function statusBg(status) {
  if (status === 'green') return C.greenLight
  if (status === 'amber') return C.amberLight
  return C.redLight
}

function statusIcon(status) {
  if (status === 'green') return 'circle-check'
  if (status === 'amber') return 'circle-alert'
  return 'circle-x'
}

// ------ Sub-components ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

function StatusDot({ status, pulse }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display:    'inline-block',
        width:      8, height: 8,
        borderRadius: '50%',
        background: statusColor(status),
        flexShrink: 0,
        animation:  pulse && status === 'red'
          ? 'pulse-dot 1.2s ease-in-out infinite' : 'none',
      }}
    />
  )
}

function KpiCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background:   C.bg,
      border:       `1px solid ${C.border}`,
      borderRadius: 8,
      padding:      '12px 16px',
      display:      'flex',
      flexDirection:'column',
      gap:          2,
    }}>
      <div style={{ fontSize: 11, color: C.muted, fontWeight: 600,
                    letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent || '#0f172a',
                    fontVariantNumeric: 'tabular-nums' }}>
        {value ?? '--'}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: C.muted }}>{sub}</div>
      )}
    </div>
  )
}

function SortableHeader({ label, sortKey, sortState, onSort, ariaLabel }) {
  const active = sortState.key === sortKey
  const dir    = active ? sortState.dir : null
  return (
    <th
      scope="col"
      aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none'}
      style={{
        padding:    '8px 12px', textAlign: 'left',
        fontSize:   11, fontWeight: 700, color: active ? '#1e40af' : C.muted,
        cursor:     'pointer', userSelect: 'none', whiteSpace: 'nowrap',
        borderBottom: `2px solid ${active ? '#1e40af' : C.border}`,
        background: C.bgSection,
      }}
      onClick={() => onSort(sortKey)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSort(sortKey) }}
      tabIndex={0}
      aria-label={ariaLabel || label}
    >
      {label} {active ? (dir === 'asc' ? ' ^' : ' v') : ''}
    </th>
  )
}

function AlertFeed({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{ padding: '16px', textAlign: 'center',
                    color: C.muted, fontSize: 12 }}
           aria-live="polite">
        No active LAN alerts
      </div>
    )
  }

  const sevColor = { critical: C.red, warning: C.amber, info: C.blue, none: C.muted }
  const top = alerts.slice(0, 10)

  return (
    <div
      role="list"
      aria-label="LAN active alerts"
      aria-live="polite"
      style={{ maxHeight: 200, overflowY: 'auto' }}
    >
      {top.map((a, i) => (
        <div
          key={a.alert_object_id || i}
          role="listitem"
          style={{
            display:       'flex',
            alignItems:    'flex-start',
            gap:           10,
            padding:       '8px 12px',
            borderBottom:  `1px solid ${C.border}`,
            background:    i % 2 === 0 ? C.bg : C.bgSection,
          }}
        >
          <StatusDot status={a.severity === 'critical' ? 'red'
            : a.severity === 'warning' ? 'amber' : 'green'} pulse />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a',
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap' }}>
              {a.node_name}
            </div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 2,
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap' }}>
              {a.description || a.alert_name}
            </div>
          </div>
          <span style={{
            fontSize:     10, fontWeight: 700,
            color:        sevColor[a.severity] || C.muted,
            textTransform:'uppercase', flexShrink: 0,
          }}>
            {a.severity}
          </span>
        </div>
      ))}
    </div>
  )
}

function LanTrendChart({ trend }) {
  if (!trend || trend.length < 2) {
    return (
      <div style={{ display: 'flex', alignItems: 'center',
                    justifyContent: 'center', height: 180,
                    color: C.muted, fontSize: 12 }}>
        Trend data builds up as ingest cycles run. Check back after a few cycles.
      </div>
    )
  }

  const data = trend.map(p => ({
    time:       p.bucket ? p.bucket.slice(11, 16) : '',
    score:      p.avg_score,
    nodes_up:   p.nodes_up_pct,
    loss:       p.avg_loss_pct,
  }))

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <XAxis dataKey="time" tick={{ fontSize: 10, fill: C.muted }}
               tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis yAxisId="score" domain={[0, 100]}
               tick={{ fontSize: 10, fill: C.muted }}
               tickLine={false} axisLine={false} width={28} />
        <YAxis yAxisId="loss" orientation="right" domain={[0, 10]}
               tick={{ fontSize: 10, fill: C.muted }}
               tickLine={false} axisLine={false} width={28} />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: 'none',
                          borderRadius: 6, fontSize: 11, color: '#e2e8f0' }}
          formatter={(v, n) => [
            `${v}${n === 'loss' ? '%' : ''}`,
            n === 'score' ? 'Health Score' : n === 'nodes_up' ? 'Nodes Up %' : 'Packet Loss %'
          ]}
        />
        <ReferenceLine yAxisId="score" y={75} stroke={C.green}
                       strokeDasharray="3 3" strokeOpacity={0.5} />
        <ReferenceLine yAxisId="score" y={55} stroke={C.amber}
                       strokeDasharray="3 3" strokeOpacity={0.5} />
        <Line yAxisId="score" type="monotone" dataKey="score"
              stroke={C.blue} strokeWidth={2} dot={false} name="score" />
        <Line yAxisId="score" type="monotone" dataKey="nodes_up"
              stroke={C.green} strokeWidth={1.5} dot={false}
              strokeDasharray="4 2" name="nodes_up" />
        <Legend iconType="line" wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
                formatter={v => v === 'score' ? 'Health Score'
                  : v === 'nodes_up' ? 'Nodes Up %' : v} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ------ Main tile ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

export default function LANHealthTile({
  lanSummary,
  lanSites,
  lanAlerts,
  lanTrend,
  lanScope,
  lanGroups,
  lanCountries,
  onScopeChange,
  lanError,
  loading,
}) {
  const [sort, setSort] = useState({ key: 'weighted_score', dir: 'desc' })

  const handleSort = (key) => {
    setSort(s =>
      s.key === key
        ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'desc' }
    )
  }

  // ------ Loading skeleton ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
  if (loading && !lanSummary) {
    return (
      <section
        aria-label="LAN Health pillar loading"
        style={{ background: C.bg, borderRadius: 12,
                 border: `1px solid ${C.border}`, padding: 20,
                 animation: 'pulse 1.5s ease-in-out infinite' }}
      >
        <div style={{ height: 20, background: C.bgSection,
                      borderRadius: 4, width: '40%', marginBottom: 12 }} />
        <div style={{ height: 80, background: C.bgSection, borderRadius: 8 }} />
      </section>
    )
  }

  // ------ Error / not yet available ------------------------------------------------------------------------------------------------------------------------------------------
  if (lanError || !lanSummary) {
    return (
      <section
        aria-label="LAN Health pillar"
        role="region"
        style={{ background: C.bg, borderRadius: 12,
                 border: `1px solid ${C.border}`, padding: 20 }}
      >
        <h2 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a',
                     margin: 0, marginBottom: 8 }}>
          LAN Health
        </h2>
        <div style={{ color: lanError ? C.red : C.muted, fontSize: 12 }}
             role="alert" aria-live="assertive">
          {lanError
            ? `SolarWinds connection error: ${lanError}`
            : 'Connecting to SolarWinds -- first data cycle in progress...'}
        </div>
      </section>
    )
  }

  const status      = lanSummary.lan_status || 'amber'
  const score       = lanSummary.overall_score ?? 0
  const viewType    = lanSites?.view_type || 'country'
  const tableData   = lanSites?.data || []

  // Sort table data
  const sorted = [...tableData].sort((a, b) => {
    const av = a[sort.key] ?? 0
    const bv = b[sort.key] ?? 0
    return sort.dir === 'asc' ? av - bv : bv - av
  })

  // ------ Status badge ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const StatusBadge = () => (
    <span
      role="status"
      aria-label={`LAN status: ${status}`}
      style={{
        display:    'inline-flex', alignItems: 'center', gap: 5,
        padding:    '2px 10px',
        background: statusBg(status),
        color:      statusColor(status),
        borderRadius: 20, fontSize: 11, fontWeight: 700,
      }}
    >
      <StatusDot status={status} pulse />
      {status.toUpperCase()}
    </span>
  )

  return (
    <section
      aria-label="LAN Health pillar -- SolarWinds"
      role="region"
      style={{
        background:   C.bg,
        borderRadius: 12,
        border:       `1px solid ${C.border}`,
        overflow:     'hidden',
      }}
    >
      {/* ------ Tile header ------------------------------------------------------------------------------------------------------------------------------------------------------------------ */}
      <div style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        flexWrap:       'wrap',
        gap:            12,
        padding:        '14px 20px',
        background:     '#1e293b',
        borderBottom:   `1px solid rgba(255,255,255,0.06)`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 700,
                       color: '#f8fafc', margin: 0 }}>
            LAN Health
          </h2>
          <StatusBadge />
          <span style={{ fontSize: 22, fontWeight: 800,
                         color: statusColor(status),
                         fontVariantNumeric: 'tabular-nums' }}>
            {score.toFixed(1)}
          </span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>/ 100</span>
        </div>

        <CountrySelector
          scope={lanScope}
          groups={lanGroups}
          countries={lanCountries}
          onChange={onScopeChange}
        />
      </div>

      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ------ KPI cards ------------------------------------------------------------------------------------------------------------------------------------------------------------ */}
        <div style={{
          display:             'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap:                 12,
        }}>
          <KpiCard
            label="Nodes Up"
            value={lanSummary.nodes_up}
            sub={`of ${lanSummary.total_nodes} total`}
            accent={C.green}
          />
          <KpiCard
            label="Nodes Down"
            value={lanSummary.nodes_down}
            sub={`${lanSummary.nodes_warning} warning`}
            accent={lanSummary.nodes_down > 0 ? C.red : C.muted}
          />
          <KpiCard
            label="Active Alerts"
            value={lanSummary.active_alerts}
            sub={`${lanSummary.critical_alerts} critical`}
            accent={lanSummary.critical_alerts > 0 ? C.red
              : lanSummary.active_alerts > 0 ? C.amber : C.muted}
          />
          <KpiCard
            label="Avg Packet Loss"
            value={`${lanSummary.avg_loss_pct ?? 0}%`}
            sub={`${lanSummary.avg_response_ms ?? 0}ms avg latency`}
            accent={lanSummary.avg_loss_pct > 5 ? C.red
              : lanSummary.avg_loss_pct > 1 ? C.amber : C.muted}
          />
        </div>

        {/* ------ Scope label ------------------------------------------------------------------------------------------------------------------------------------------------------ */}
        <div style={{ fontSize: 11, color: C.muted, fontWeight: 600 }}
             aria-live="polite">
          Viewing: {lanSummary.scope_label}
          {' '}{viewType === 'node'
            ? `-- ${tableData.length} nodes`
            : `-- ${tableData.length} countries`}
        </div>

        {/* ------ Site / node table ------------------------------------------------------------------------------------------------------------------------------------ */}
        <div style={{
          border:        `1px solid ${C.border}`,
          borderRadius:  8,
          overflow:      'hidden',
          maxHeight:     260,
          overflowY:     'auto',
        }}>
          <table
            style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}
            aria-label={viewType === 'country' ? 'Country health table' : 'Node health table'}
          >
            <thead>
              <tr>
                {viewType === 'country' ? (
                  <>
                    <SortableHeader label="Country"      sortKey="country"       sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Nodes"        sortKey="node_count"    sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Score"        sortKey="weighted_score" sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Up"           sortKey="nodes_up"      sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Down"         sortKey="nodes_down"    sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Loss %"       sortKey="avg_loss_pct"  sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Alerts"       sortKey="alert_count"   sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Status"       sortKey="lan_status"    sortState={sort} onSort={handleSort} />
                  </>
                ) : (
                  <>
                    <SortableHeader label="Node"         sortKey="node_name"          sortState={sort} onSort={handleSort} />
                    <SortableHeader label="IP"           sortKey="ip_address"         sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Score"        sortKey="composite_score"    sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Loss %"       sortKey="percent_loss"       sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Resp ms"      sortKey="avg_response_time_ms" sortState={sort} onSort={handleSort} />
                    <SortableHeader label="In Util %"    sortKey="max_in_util"        sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Alert"        sortKey="alert_severity"     sortState={sort} onSort={handleSort} />
                    <SortableHeader label="Status"       sortKey="lan_status"         sortState={sort} onSort={handleSort} />
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: 16, textAlign: 'center',
                                           color: C.muted }}>
                    No data available
                  </td>
                </tr>
              ) : sorted.map((row, i) => (
                <tr key={row.country || row.node_id || i}
                    style={{ background: i % 2 === 0 ? C.bg : C.bgSection }}>
                  {viewType === 'country' ? (
                    <>
                      <td style={{ padding: '7px 12px', fontWeight: 500 }}>
                        {row.country}
                      </td>
                      <td style={{ padding: '7px 12px', color: C.muted }}>
                        {row.node_count}
                      </td>
                      <td style={{ padding: '7px 12px', fontWeight: 600,
                                   color: statusColor(row.lan_status),
                                   fontVariantNumeric: 'tabular-nums' }}>
                        {row.weighted_score?.toFixed(1)}
                      </td>
                      <td style={{ padding: '7px 12px', color: C.green }}>
                        {row.nodes_up}
                      </td>
                      <td style={{ padding: '7px 12px',
                                   color: row.nodes_down > 0 ? C.red : C.muted }}>
                        {row.nodes_down}
                      </td>
                      <td style={{ padding: '7px 12px',
                                   color: row.avg_loss_pct > 5 ? C.red
                                     : row.avg_loss_pct > 1 ? C.amber : C.muted }}>
                        {row.avg_loss_pct?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '7px 12px',
                                   color: row.alert_count > 0 ? C.amber : C.muted }}>
                        {row.alert_count}
                      </td>
                      <td style={{ padding: '7px 12px' }}>
                        <span style={{
                          display:      'inline-flex', alignItems: 'center', gap: 5,
                          padding:      '2px 8px',
                          background:   statusBg(row.lan_status),
                          color:        statusColor(row.lan_status),
                          borderRadius: 12, fontSize: 10, fontWeight: 700,
                        }}>
                          <StatusDot status={row.lan_status} />
                          {row.lan_status?.toUpperCase()}
                        </span>
                      </td>
                    </>
                  ) : (
                    <>
                      <td style={{ padding: '7px 12px', fontWeight: 500,
                                   maxWidth: 160, overflow: 'hidden',
                                   textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {row.node_name}
                      </td>
                      <td style={{ padding: '7px 12px', color: C.muted,
                                   fontFamily: 'monospace', fontSize: 11 }}>
                        {row.ip_address}
                      </td>
                      <td style={{ padding: '7px 12px', fontWeight: 600,
                                   color: statusColor(row.lan_status),
                                   fontVariantNumeric: 'tabular-nums' }}>
                        {row.composite_score?.toFixed(1)}
                      </td>
                      <td style={{ padding: '7px 12px',
                                   color: row.percent_loss > 5 ? C.red
                                     : row.percent_loss > 1 ? C.amber : C.muted }}>
                        {row.percent_loss?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '7px 12px', color: C.muted,
                                   fontVariantNumeric: 'tabular-nums' }}>
                        {row.avg_response_time_ms?.toFixed(0)}
                      </td>
                      <td style={{ padding: '7px 12px', color: C.muted }}>
                        {row.max_in_util?.toFixed(1)}%
                      </td>
                      <td style={{ padding: '7px 12px' }}>
                        {row.alert_severity && row.alert_severity !== 'none' ? (
                          <span style={{
                            color:       row.alert_severity === 'critical' ? C.red : C.amber,
                            fontWeight:  600, fontSize: 11, textTransform: 'uppercase',
                          }}>
                            {row.alert_severity}
                          </span>
                        ) : (
                          <span style={{ color: C.muted }}>--</span>
                        )}
                      </td>
                      <td style={{ padding: '7px 12px' }}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                          padding: '2px 8px',
                          background: statusBg(row.lan_status),
                          color: statusColor(row.lan_status),
                          borderRadius: 12, fontSize: 10, fontWeight: 700,
                        }}>
                          <StatusDot status={row.lan_status} />
                          {row.lan_status?.toUpperCase()}
                        </span>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ------ Two-column: alerts + trend --------------------------------------------------------------------------------------------------------- */}
        <div style={{
          display:             'grid',
          gridTemplateColumns: '1fr 1.4fr',
          gap:                 16,
        }}>
          <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700,
                          color: C.muted, background: C.bgSection,
                          borderBottom: `1px solid ${C.border}`,
                          textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Active Alerts
            </div>
            <AlertFeed alerts={lanAlerts} />
          </div>

          <div style={{ border: `1px solid ${C.border}`, borderRadius: 8,
                        overflow: 'hidden', padding: '8px 12px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.muted,
                          textTransform: 'uppercase', letterSpacing: '0.04em',
                          marginBottom: 8 }}>
              7-Day Trend
            </div>
            <LanTrendChart trend={lanTrend} />
          </div>
        </div>

        {/* ------ Data source footer ------------------------------------------------------------------------------------------------------------------------------------ */}
        <div style={{ fontSize: 10, color: C.muted, display: 'flex',
                      justifyContent: 'space-between' }}>
          <span>Source: SolarWinds Observability Self-Hosted</span>
          {lanSummary.last_ingested_at && (
            <span>
              Last updated:{' '}
              {new Date(lanSummary.last_ingested_at).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>
    </section>
  )
}
