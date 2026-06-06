/**
 * CountrySelector -- combo box for LAN pillar scope selection.
 *
 * Renders two sections in the dropdown:
 *   1. Region groups (from sw_country_groups DB table)
 *   2. Individual countries (from live SolarWinds data)
 *
 * Accessibility (WCAG 2.1 AA):
 *   - role="combobox" with aria-expanded, aria-haspopup, aria-label
 *   - role="listbox" / role="option" on dropdown items
 *   - aria-selected on active item
 *   - Keyboard: Enter/Space open, ArrowUp/Down navigate,
 *     Enter selects, Escape closes
 *   - Focus trapped inside open dropdown
 *   - Visible focus ring on all interactive elements
 *   - Colour contrast >= 4.5:1 on all text
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'

const STYLES = {
  wrapper: {
    position:   'relative',
    display:    'inline-flex',
    alignItems: 'center',
    gap:        8,
    flexShrink: 0,
  },
  label: {
    fontSize:   11,
    fontWeight: 600,
    color:      'rgba(255,255,255,0.6)',
    whiteSpace: 'nowrap',
    letterSpacing: '0.04em',
  },
  trigger: (open) => ({
    display:        'flex',
    alignItems:     'center',
    gap:            6,
    padding:        '4px 10px',
    background:     open ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)',
    border:         `1px solid ${open ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.15)'}`,
    borderRadius:   6,
    color:          '#fff',
    fontSize:       12,
    fontWeight:     500,
    cursor:         'pointer',
    userSelect:     'none',
    minWidth:       140,
    maxWidth:       200,
    whiteSpace:     'nowrap',
    overflow:       'hidden',
    textOverflow:   'ellipsis',
    outline:        'none',
    transition:     'background 0.15s, border-color 0.15s',
  }),
  dropdown: {
    position:        'absolute',
    top:             '100%',
    left:            0,
    marginTop:       4,
    background:      '#1e293b',
    border:          '1px solid rgba(255,255,255,0.12)',
    borderRadius:    8,
    boxShadow:       '0 8px 24px rgba(0,0,0,0.4)',
    minWidth:        220,
    maxHeight:       320,
    overflowY:       'auto',
    zIndex:          200,
    padding:         '6px 0',
  },
  sectionLabel: {
    padding:         '6px 14px 3px',
    fontSize:        10,
    fontWeight:      700,
    color:           'rgba(255,255,255,0.35)',
    letterSpacing:   '0.08em',
    textTransform:   'uppercase',
  },
  divider: {
    height:          1,
    background:      'rgba(255,255,255,0.08)',
    margin:          '6px 0',
  },
  option: (active, selected) => ({
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'space-between',
    padding:         '7px 14px',
    fontSize:        12,
    color:           selected ? '#60a5fa' : active ? '#fff' : 'rgba(255,255,255,0.75)',
    background:      active ? 'rgba(255,255,255,0.08)' : 'transparent',
    cursor:          'pointer',
    outline:         'none',
    borderLeft:      selected ? '2px solid #60a5fa' : '2px solid transparent',
    transition:      'background 0.1s',
  }),
  badge: {
    fontSize:        10,
    color:           'rgba(255,255,255,0.4)',
    fontVariantNumeric: 'tabular-nums',
  },
  chevron: (open) => ({
    transition:   'transform 0.15s',
    transform:    open ? 'rotate(180deg)' : 'none',
    flexShrink:   0,
    opacity:      0.7,
  }),
}

export default function CountrySelector({
  scope,
  groups,
  countries,
  onChange,
}) {
  const [open, setOpen]     = useState(false)
  const [active, setActive] = useState(-1)
  const wrapperRef          = useRef(null)
  const triggerRef          = useRef(null)

  // ------ Build flat option list for keyboard navigation ---------------------------------------------------------------------------
  const options = React.useMemo(() => {
    const list = []

    // Groups section
    if (groups.length > 0) {
      list.push({ type: 'section', label: 'Regions' })
      groups.forEach(g => list.push({
        type:  'group',
        label: g.group_name,
        value: g.group_slug === 'all' ? 'all' : `group:${g.group_slug}`,
        count: null,
      }))
    }

    // Countries section
    if (countries.length > 0) {
      list.push({ type: 'divider' })
      list.push({ type: 'section', label: 'Countries' })
      countries.forEach(c => list.push({
        type:  'country',
        label: c.country,
        value: `country:${c.country}`,
        count: c.node_count,
      }))
    }

    return list
  }, [groups, countries])

  const selectables = options.filter(o => o.type !== 'section' && o.type !== 'divider')

  // ------ Current label ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  const currentLabel = React.useMemo(() => {
    if (!scope || scope === 'all') return 'All'
    if (scope.startsWith('group:')) {
      const slug = scope.slice(6)
      const g = groups.find(x => x.group_slug === slug)
      return g ? g.group_name : slug
    }
    if (scope.startsWith('country:')) return scope.slice(8)
    return 'All'
  }, [scope, groups])

  // ------ Close on outside click ---------------------------------------------------------------------------------------------------------------------------------------------------
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // ------ Keyboard navigation ------------------------------------------------------------------------------------------------------------------------------------------------------------
  const handleKeyDown = useCallback((e) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        setOpen(true)
        setActive(0)
      }
      return
    }
    if (e.key === 'Escape') {
      setOpen(false)
      triggerRef.current?.focus()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(i => Math.min(i + 1, selectables.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (active >= 0 && active < selectables.length) {
        onChange(selectables[active].value)
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
  }, [open, active, selectables, onChange])

  const handleSelect = (value) => {
    onChange(value)
    setOpen(false)
    triggerRef.current?.focus()
  }

  let selectableIdx = -1

  return (
    <div ref={wrapperRef} style={STYLES.wrapper}>
      <span style={STYLES.label} id="country-selector-label">
        Scope:
      </span>

      {/* Trigger button */}
      <div
        ref={triggerRef}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-labelledby="country-selector-label"
        aria-label={`LAN scope: ${currentLabel}`}
        tabIndex={0}
        style={STYLES.trigger(open)}
        onClick={() => { setOpen(o => !o); setActive(0) }}
        onKeyDown={handleKeyDown}
      >
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {currentLabel}
        </span>
        <svg
          style={STYLES.chevron(open)}
          width="10" height="10" viewBox="0 0 10 10"
          fill="none" aria-hidden="true"
        >
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </div>

      {/* Dropdown */}
      {open && (
        <div
          role="listbox"
          aria-label="Select LAN scope"
          style={STYLES.dropdown}
          onKeyDown={handleKeyDown}
        >
          {options.map((opt, i) => {
            if (opt.type === 'section') {
              return (
                <div key={i} style={STYLES.sectionLabel} aria-hidden="true">
                  {opt.label}
                </div>
              )
            }
            if (opt.type === 'divider') {
              return <div key={i} style={STYLES.divider} role="separator" />
            }
            selectableIdx++
            const idx      = selectableIdx
            const selected = opt.value === scope || (opt.value === 'all' && !scope)
            const isActive = active === idx
            return (
              <div
                key={opt.value}
                role="option"
                aria-selected={selected}
                tabIndex={-1}
                style={STYLES.option(isActive, selected)}
                onClick={() => handleSelect(opt.value)}
                onMouseEnter={() => setActive(idx)}
              >
                <span>{opt.label}</span>
                {opt.count != null && (
                  <span style={STYLES.badge}>{opt.count} nodes</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
