import { createElement as h } from 'react'
import { AlertTriangle, Clock3, Database, Route, ShieldAlert } from 'lucide-react'

function Pill({ children, tone = 'neutral' }) {
  return h('span', { className: `pill pill-${tone}` }, children)
}

function Panel({ title, subtitle, action, className = '', children }) {
  return h('section', { className: `panel ${className}` },
    h('div', { className: 'panel-heading' },
      h('div', null,
        h('h2', null, title),
        subtitle && h('p', null, subtitle),
      ),
      action,
    ),
    children,
  )
}

function formatDuration(minutes) {
  if (!Number.isFinite(minutes)) return 'Unavailable'
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return hours ? `${hours} hr ${remainingMinutes} min` : `${remainingMinutes} min`
}

function RouteMetrics({ assessment }) {
  return h('div', { className: 'route-metric-grid' },
    h('div', { className: 'route-metric' },
      h(Route, { size: 16 }),
      h('span', null, 'Distance'),
      h('strong', null, `${assessment.distance_km.toLocaleString()} km`),
    ),
    h('div', { className: 'route-metric' },
      h(Clock3, { size: 16 }),
      h('span', null, 'Estimated time'),
      h('strong', null, formatDuration(assessment.duration_minutes)),
    ),
  )
}

function RouteFactors({ factors }) {
  if (!factors.length) return null
  return h('div', { className: 'route-factor-list', 'aria-label': 'Route risk factors' },
    factors.map((factor, index) => h('div', {
      className: `route-factor route-factor-${factor.severity?.toLowerCase().replace(' ', '-')}`,
      key: `${factor.type}-${index}`,
    },
    h(AlertTriangle, { size: 14 }),
    h('span', null, factor.detail),
    )),
  )
}

function formatTimestamp(value) {
  if (!value) return 'Timestamp unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : date.toLocaleString()
}

function FloodObservations({ observations, reportStatus }) {
  if (!observations.length) {
    if (reportStatus === 'none') return h('div', { className: 'route-data-note' },
      h(Database, { size: 15 }),
      'No nearby citizen flood reports were found. Absence of reports does not establish road safety.',
    )
    if (reportStatus === 'insufficient_location_data') return h('div', { className: 'route-data-note route-data-note-warning' },
      h(Database, { size: 15 }),
      'Citizen reports exist, but some lack usable coordinates, so they could not be matched to the route.',
    )
    return null
  }
  return h(Panel, {
    title: 'Citizen flood reports near route',
    subtitle: 'Citizen-submitted reports are indicators, not official confirmation',
  }, h('div', { className: 'route-observation-list' },
    observations.map((observation) => h('article', {
      className: 'route-observation',
      key: observation.report_id,
    },
    h('span', { className: `route-observation-dot route-observation-${observation.verification_status}` }),
    h('div', null,
      h('strong', null, `Citizen report · ${observation.verification_status} · ${observation.severity || 'severity unavailable'} · ${observation.distance_from_route_m} m from route`),
      h('span', null, observation.location_name || 'Location name unavailable'),
      h('span', null, observation.description || 'No report description provided'),
      h('span', null, `Reported: ${formatTimestamp(observation.created_at)}. Citizen-submitted; not an official road warning.`),
    ),
    )),
  ))
}

function SachetObservations({ sachet }) {
  const observations = sachet?.alerts || []
  return h(Panel, {
    title: 'Official SACHET alerts near route',
    subtitle: sachet?.last_successful_check_at
      ? `Official source snapshot checked: ${formatTimestamp(sachet.last_successful_check_at)}`
      : 'Official source snapshot time unavailable',
  }, h('div', { className: 'route-observation-list' },
    observations.length
      ? observations.map((alert) => h('article', {
          className: 'route-observation',
          key: alert.alert_id,
        },
        h('span', { className: 'route-observation-dot route-observation-official' }),
        h('div', null,
          h('strong', null, `Official SACHET alert · ${alert.distance_from_route_m} m from route`),
          h('span', null, alert.headline || 'Headline unavailable'),
          h('span', null, alert.description || 'Official description unavailable'),
          h('span', null, `Source: ${alert.source_name || 'NDMA SACHET'} · Published: ${formatTimestamp(alert.source_published_at)}${alert.source_url ? ` · ${alert.source_url}` : ''}`),
        ),
      ))
      : h('p', { className: 'route-data-note' },
          h(Database, { size: 15 }),
          sachet?.alerts_without_coordinates
            ? `${sachet.alerts_without_coordinates} official alert(s) lack usable coordinates and were not placed on the map.`
            : 'No geographically matched SACHET alerts were found near this route.',
        ),
  ))
}

function RouteAlternatives({ alternatives }) {
  if (!alternatives.length) return null
  return h(Panel, {
    title: 'OSRM alternatives',
    subtitle: 'Alternative geometry is from OSRM; flood risk was not separately assessed',
  }, h('div', { className: 'route-alternative-list' },
    alternatives.map((alternative, index) => h('article', {
      className: 'route-alternative',
      key: `alternative-${index}`,
    },
    h('span', null, `Alternative ${index + 1}`),
    h('strong', null, `${(alternative.distance_m / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })} km`),
    h('strong', null, formatDuration(Math.round(alternative.duration_s / 60))),
    h(Pill, { tone: 'neutral' }, 'NOT ASSESSED'),
    )),
  ))
}

export function RouteDetails({ assessment }) {
  const riskLevel = assessment.risk_classification.level
  const riskTone = riskLevel === 'High' ? 'red' : riskLevel === 'Moderate' ? 'amber' : 'teal'
  const observations = assessment.flood_observations?.observations || []
  const factors = assessment.risk_factors || []
  const hazardCount = observations.length + (assessment.sachet_alerts?.alerts?.length || 0)
  const hazardLabel = hazardCount === 0
    ? 'No nearby reported hazards found'
    : hazardCount === 1
      ? 'Nearby reported flood hazards'
      : 'Multiple nearby reported hazards'
  const children = [
    h(RouteMetrics, { assessment, key: 'metrics' }),
    h('p', { className: 'route-hazard-summary', key: 'hazard-summary' },
      h(ShieldAlert, { size: 16 }),
      h('strong', null, hazardLabel),
      h('span', null, `${hazardCount} geographically nearby hazard indicator(s) within ${assessment.hazard_proximity_m || 500} m of the route geometry.`),
    ),
    h('p', { className: 'route-risk-explanation', key: 'explanation' },
      h(ShieldAlert, { size: 16 }),
      assessment.risk_classification.explanation,
    ),
  ]

  if (assessment.flood_observations?.status === 'unavailable') {
    children.push(h('p', { className: 'route-data-note route-data-note-warning', key: 'report-error' },
      h(Database, { size: 15 }),
      'Citizen flood-report data could not be checked because MongoDB is unavailable.',
    ))
  }
  children.push(h(RouteFactors, { factors, key: 'factors' }))
  children.push(h('p', { className: 'route-limitation', key: 'limitations' }, assessment.limitations))

  return h('div', { className: 'route-details-stack' },
    h(Panel, {
      className: 'route-result-panel',
      title: 'Route assessment',
      subtitle: 'OSRM driving route · provider-estimated travel time',
      action: h(Pill, { tone: riskTone }, `${riskLevel.toUpperCase()} RISK`),
    }, children),
    h(FloodObservations, {
      observations,
      reportStatus: assessment.flood_observations?.status,
      key: 'observations',
    }),
    h(SachetObservations, { sachet: assessment.sachet_alerts, key: 'sachet-alerts' }),
    h(RouteAlternatives, { alternatives: assessment.alternatives || [], key: 'alternatives' }),
  )
}

export function RouteLoading() {
  return h('div', { className: 'route-loading', role: 'status', 'aria-live': 'polite' },
    'Requesting a road route and checking available risk data…',
  )
}
