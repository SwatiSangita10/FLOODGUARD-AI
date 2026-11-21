import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import {
  AlertCard,
  EmptyEmergencyState,
  ResourceCard,
  SachetFeedStatus,
} from '../src/components/EmergencyCards.js'
import {
  getAlertClientId,
  getSachetFeed,
  listAlerts,
  listResources,
  markAlertRead,
} from '../src/services/emergencyApi.js'

const resource = {
  resource_id: 'resource-1',
  name: 'Community medical centre',
  category: 'hospital',
  address: 'Main Road',
  district: 'Khordha',
  latitude: 20.3,
  longitude: 85.8,
  contact_number: '+91 674 1234567',
  operating_hours: '09:00–17:00',
  source_name: 'Official district directory',
  source_url: 'https://odisha.gov.in/en/contacts/emergency',
  verification_status: 'verified',
  last_verified_at: '2025-01-01T10:00:00Z',
}

const alert = {
  alert_id: 'weather:20.3000:85.8000',
  title: 'Weather-based flood advisory',
  description: 'Open-Meteo indicates elevated precipitation; this is not an official warning.',
  severity: 'Advisory',
  affected_location: 'Bhubaneswar',
  district: null,
  source_type: 'weather',
  source_name: 'Open-Meteo',
  source_url: 'https://open-meteo.com/',
  source_verification_status: 'not_applicable',
  source_published_at: '2025-01-01T10:00:00Z',
  last_verified_at: null,
  created_at: '2025-01-01T10:00:00Z',
  expires_at: null,
  status: 'active',
  source_record_id: null,
  is_read: false,
}

test('resource records expose verified source, call, and directions actions only when appropriate', () => {
  const verifiedMarkup = renderToStaticMarkup(createElement(ResourceCard, { resource }))
  assert.match(verifiedMarkup, /Verified/)
  assert.match(verifiedMarkup, /Official district directory/)
  assert.match(verifiedMarkup, /tel:\+916741234567/)
  assert.match(verifiedMarkup, /openstreetmap\.org/)
  assert.match(verifiedMarkup, /not a live open-status check/)

  const unverifiedMarkup = renderToStaticMarkup(createElement(ResourceCard, {
    resource: { ...resource, verification_status: 'unverified', latitude: null, longitude: null },
  }))
  assert.match(unverifiedMarkup, /Unverified/)
  assert.match(unverifiedMarkup, /do not rely on it/)
  assert.doesNotMatch(unverifiedMarkup, /href="tel:/)
  assert.doesNotMatch(unverifiedMarkup, /openstreetmap\.org/)
})

test('facility cards support shelter categories and do not invent location or capacity data', () => {
  const markup = renderToStaticMarkup(createElement(ResourceCard, {
    resource: {
      ...resource,
      category: 'multipurpose_flood_shelter',
      name: 'CMRF shelter listing 2',
      address: 'Community place in the entrance of the village',
      district: 'Baragada',
      block: 'Ambabhona',
      village: 'Ganthiapali',
      state: 'Odisha',
      latitude: null,
      longitude: null,
      contact_number: null,
      capacity: null,
      verification_status: 'unverified',
      last_verified_at: null,
    },
  }))
  assert.match(markup, /Multipurpose flood shelter/)
  assert.match(markup, /Ambabhona/)
  assert.match(markup, /Baragada/)
  assert.match(markup, /Source has not been verified/)
  assert.doesNotMatch(markup, /Published capacity/)
  assert.doesNotMatch(markup, /openstreetmap\.org/)
})

test('resource page includes verified-empty guidance and the required availability disclaimer', () => {
  const source = readFileSync(
    new URL('../src/pages/ResourcesPage.jsx', import.meta.url),
    'utf8',
  )
  assert.match(source, /No verified facilities are currently available/)
  assert.match(source, /Loading resource directory/)
  assert.match(source, /Resource directory unavailable/)
  assert.match(
    source,
    /Facility information is based on cited official sources\. Availability, operating status and emergency access must be confirmed with the relevant authorities\./,
  )
})

test('alert cards display severity, source qualification, read status, and detail navigation', () => {
  const markup = renderToStaticMarkup(createElement(
    MemoryRouter,
    null,
    createElement(AlertCard, { alert }),
  ))
  assert.match(markup, /Advisory/)
  assert.match(markup, /Weather-based advisory · not official/)
  assert.match(markup, /Unread/)
  assert.match(markup, /View alert details/)
  assert.match(markup, /\/alerts\/weather%3A20\.3000%3A85\.8000/)

  const readMarkup = renderToStaticMarkup(createElement(
    MemoryRouter,
    null,
    createElement(AlertCard, { alert: { ...alert, is_read: true } }),
  ))
  assert.match(readMarkup, /Read/)
  assert.doesNotMatch(readMarkup, /Mark as read/)
})

test('SACHET cards preserve missing severity, area, description, and validity honestly', () => {
  const markup = renderToStaticMarkup(createElement(
    MemoryRouter,
    null,
    createElement(AlertCard, {
      alert: {
        ...alert,
        alert_id: 'sachet:official-id',
        title: 'Official SACHET headline',
        description: null,
        severity: null,
        affected_location: null,
        source_type: 'sachet',
        source_name: 'NDMA SACHET',
        source_url: 'https://sachet.ndma.gov.in/alert/official-id',
        source_published_at: null,
        status: 'feed_entry',
      },
    }),
  ))
  assert.match(markup, /Official SACHET feed entry/)
  assert.match(markup, /Publication time not provided in RSS/)
  assert.match(markup, /Description not provided in the RSS feed/)
  assert.match(markup, /Affected area not provided in RSS/)
  assert.match(markup, /does not confirm whether the alert is still valid/)
  assert.match(markup, /https:\/\/sachet\.ndma\.gov\.in\/alert\/official-id/)
  assert.doesNotMatch(markup, /Advisory/)
})

test('emergency loading, error, and empty states are accessible', () => {
  const loadingMarkup = renderToStaticMarkup(createElement(EmptyEmergencyState, {
    loading: true,
    title: 'Loading alerts',
    description: 'Checking current records.',
  }))
  const errorMarkup = renderToStaticMarkup(createElement(EmptyEmergencyState, {
    error: true,
    title: 'Alerts unavailable',
    description: 'MongoDB is unavailable.',
  }))
  const emptyMarkup = renderToStaticMarkup(createElement(EmptyEmergencyState, {
    title: 'No active alerts available',
    description: 'Check official sources.',
  }))
  assert.match(loadingMarkup, /role="status"/)
  assert.match(errorMarkup, /role="alert"/)
  assert.match(emptyMarkup, /No active alerts available/)
})

test('SACHET feed status distinguishes loading, checked-empty, stale, and unavailable states', () => {
  const loadingMarkup = renderToStaticMarkup(createElement(SachetFeedStatus, {
    loading: true,
  }))
  const emptyMarkup = renderToStaticMarkup(createElement(SachetFeedStatus, {
    feed: { status: 'empty', count: 0 },
  }))
  const staleMarkup = renderToStaticMarkup(createElement(SachetFeedStatus, {
    feed: { status: 'stale', count: 1 },
  }))
  const unavailableMarkup = renderToStaticMarkup(createElement(SachetFeedStatus, {
    feed: { status: 'unavailable', count: 0 },
  }))
  const errorMarkup = renderToStaticMarkup(createElement(SachetFeedStatus, {
    error: 'Backend request failed',
  }))
  assert.match(loadingMarkup, /role="status"/)
  assert.match(emptyMarkup, /returned no unexpired entries/)
  assert.match(emptyMarkup, /does not establish that no hazard exists/)
  assert.match(staleMarkup, /role="alert"/)
  assert.match(staleMarkup, /previously retrieved entries are retained/)
  assert.match(unavailableMarkup, /Current official alert status is unknown/)
  assert.doesNotMatch(unavailableMarkup, /No active official alerts/)
  assert.match(errorMarkup, /role="alert"/)
  assert.match(errorMarkup, /feed and its cached entries could not be loaded/)
})

test('resource search and verification filters are sent to the backend', async () => {
  let url = ''
  const response = await listResources({
    category: 'hospital',
    district: 'Khordha',
    search: 'Clinic 1',
    verification_status: 'verified',
    is_active: false,
    limit: 10,
    offset: 20,
  }, {
    fetchImpl: async (requestUrl) => {
      url = requestUrl
      return { ok: true, json: async () => ({ count: 0, results: [] }) }
    },
  })
  const params = new URL(url).searchParams
  assert.equal(params.get('category'), 'hospital')
  assert.equal(params.get('district'), 'Khordha')
  assert.equal(params.get('search'), 'Clinic 1')
  assert.equal(params.get('verification_status'), 'verified')
  assert.equal(params.get('is_active'), 'false')
  assert.equal(params.get('offset'), '20')
  assert.deepEqual(response, { count: 0, results: [] })
})

test('SACHET feed requests go through the FLOODGUARD backend endpoint', async () => {
  let url = ''
  const result = await getSachetFeed({
    fetchImpl: async (requestUrl) => {
      url = requestUrl
      return {
        ok: true,
        json: async () => ({ status: 'available', alerts: [] }),
      }
    },
  })
  assert.equal(new URL(url).pathname, '/api/alerts/sachet/')
  assert.deepEqual(result, { status: 'available', alerts: [] })
})

test('alert listing supplies non-identifying read identity and optional area filters', async () => {
  let url = ''
  const response = await listAlerts({
    severity: 'Warning',
    district: 'Khordha',
    client_id: '123e4567-e89b-42d3-a456-426614174000',
    latitude: 20.3,
    longitude: 85.8,
    location_name: 'Bhubaneswar',
  }, {
    fetchImpl: async (requestUrl) => {
      url = requestUrl
      return { ok: true, json: async () => ({ count: 0, unread_count: 0, results: [] }) }
    },
  })
  const params = new URL(url).searchParams
  assert.equal(params.get('severity'), 'Warning')
  assert.equal(params.get('district'), 'Khordha')
  assert.equal(params.get('client_id'), '123e4567-e89b-42d3-a456-426614174000')
  assert.equal(params.get('latitude'), '20.3')
  assert.equal(params.get('location_name'), 'Bhubaneswar')
  assert.equal(response.unread_count, 0)
})

test('mark-read persists only an alert id and browser-scoped UUID; API failures surface', async () => {
  let options
  await markAlertRead('alert-1', '123e4567-e89b-42d3-a456-426614174000', {
    fetchImpl: async (_url, requestOptions) => {
      options = requestOptions
      return { ok: true, json: async () => ({ alert_id: 'alert-1', is_read: true }) }
    },
  })
  assert.equal(options.method, 'POST')
  assert.deepEqual(JSON.parse(options.body), {
    alert_id: 'alert-1',
    client_id: '123e4567-e89b-42d3-a456-426614174000',
  })
  await assert.rejects(
    listAlerts({}, { fetchImpl: async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Alert database unavailable.' }) }) }),
    /Alert database unavailable/,
  )
  assert.equal(getAlertClientId(), '')
})

test('resource and alert pages define responsive controls and no fake-data fallbacks', () => {
  const resources = readFileSync(new URL('../src/pages/ResourcesPage.jsx', import.meta.url), 'utf8')
  const alerts = readFileSync(new URL('../src/pages/AlertsPage.jsx', import.meta.url), 'utf8')
  const overview = readFileSync(new URL('../src/pages/OverviewPage.jsx', import.meta.url), 'utf8')
  const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')
  assert.match(resources, /listResources/)
  assert.match(resources, /resource-district/)
  assert.match(alerts, /listAlerts/)
  assert.match(alerts, /No active alerts available/)
  assert.doesNotMatch(overview, /demoAlerts|demoReports|demoResources/)
  assert.match(css, /@media \(max-width: 600px\)[\s\S]*?\.emergency-filter-grid/)
})
