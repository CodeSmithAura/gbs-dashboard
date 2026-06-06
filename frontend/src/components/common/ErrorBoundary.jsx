/**
 * ErrorBoundary -- React error boundary for pillar-level fault isolation.
 *
 * Catches JavaScript errors in child components and renders a fallback
 * instead of crashing the entire dashboard.
 *
 * Usage:
 *   <ErrorBoundary pillar="LAN Health">
 *     <LANHealthTile ... />
 *   </ErrorBoundary>
 *
 * Accessibility:
 *   - role="alert" on error state -- announced by screen readers
 *   - aria-live="assertive" -- immediate announcement
 *   - Retry button is keyboard focusable
 */

import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    // Log to console in development -- replace with error reporting in production
    console.error(
      `[ErrorBoundary] ${this.props.pillar || 'Component'} crashed:`,
      error,
      info.componentStack
    )
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div
        role="alert"
        aria-live="assertive"
        style={{
          background:   '#fef2f2',
          border:       '1px solid #fca5a5',
          borderRadius: 12,
          padding:      '24px 28px',
          display:      'flex',
          flexDirection:'column',
          gap:          12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            aria-hidden="true"
            style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#dc2626', flexShrink: 0,
            }}
          />
          <strong style={{ fontSize: 14, color: '#991b1b' }}>
            {this.props.pillar || 'Dashboard'} encountered an error
          </strong>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: '#7f1d1d' }}>
          An unexpected error occurred in this panel. The rest of the
          dashboard continues to operate normally.
        </p>
        <button
          onClick={this.handleRetry}
          style={{
            alignSelf:    'flex-start',
            padding:      '6px 16px',
            background:   '#dc2626',
            color:        '#fff',
            border:       'none',
            borderRadius: 6,
            fontSize:     12,
            fontWeight:   600,
            cursor:       'pointer',
          }}
          aria-label={`Retry ${this.props.pillar || 'panel'}`}
        >
          Retry
        </button>
      </div>
    )
  }
}
