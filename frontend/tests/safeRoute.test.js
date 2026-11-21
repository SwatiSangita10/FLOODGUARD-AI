import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { RouteDetails, RouteLoading } from '../src/components/RouteDetails.js'
import {
  findSafeRoute,
  getRouteFormError,
  initialRouteFinderState,
  routeFinderReducer,
} from '../src/services/safeRouteApi.js'

const origin = { name: 'Origin', latitude: 20.3, longitude: 85.8 }
const destination = { name: 'Destination', latitude: 20.32, longitude: 85.83 }

const assessment = {
  route: {
    geometry: { type: 'LineString', coordinates: [[85.8, 20.3], [85.83, 20.32]] },
    distance_m: 5400,
    duration_s: 900,
  },
  distance_km: 5.4,
  duration_minutes: 15,
  risk_classification: { level: 'High', explanation: 'A verified report is near the route.' },
  risk_factors: [{ type: 'verified_flood_report', severity: 'moderate', detail: 'Verified report near route.' }],
  flood_observations: {
    status: 'available',
    observations: [{
      report_id: 'report-1',
      location_name: 'Test locality',
      severity: 'moderate',
      verification_status: 'verified',
      distance_from_route_m: 25,
      description: 'Waterlogging on the road.',
      created_at: '2026-11-20T10:00:00Z',
    }],
  },
  sachet_alerts: {
    status: 'available',
    count: 1,
    alerts_without_coordinates: 0,
    last_successful_check_at: '2026-11-21T10:00:00Z',
    alerts: [{
      alert_id: 'sachet:test',
      headline: 'Official flood alert',
      description: 'Follow official instructions.',
      source_name: 'NDMA SACHET',
      source_url: 'https://sachet.ndma.gov.in/alert/test',
      source_published_at: '2026-11-21T09:00:00Z',
      distance_from_route_m: 40,
    }],
  },
  alternatives: [{
    distance_m: 6000,
    duration_s: 1000,
    geometry: { type: 'LineString', coordinates: [[85.8, 20.3], [85.83, 20.32]] },
  }],
  limitations: 'Road conditions can change quickly.',
}

test('route form rejects missing, invalid, and identical locations', () => {
  assert.match(getRouteFormError(null, destination), /starting point/)
  assert.match(getRouteFormError(origin, { ...destination, latitude: 91 }), /invalid coordinates/)
  assert.match(getRouteFormError(origin, { ...origin }), /different/)
  assert.equal(getRouteFormError(origin, destination), '')
})

test('route finder reducer represents loading, success, failure, and reset states', () => {
  const loading = routeFinderReducer(initialRouteFinderState, { type: 'start' })
  assert.equal(loading.status, 'loading')
  assert.equal(loading.route, null)

  const success = routeFinderReducer(loading, { type: 'success', route: assessment })
  assert.equal(success.status, 'success')
  assert.equal(success.route, assessment)

  const failure = routeFinderReducer(loading, { type: 'failure', error: 'OSRM unavailable.' })
  assert.equal(failure.status, 'error')
  assert.equal(failure.error, 'OSRM unavailable.')
  assert.equal(routeFinderReducer(failure, { type: 'reset' }).status, 'idle')
})

test('loading and successful route details render accessible status and real metrics', () => {
  const loadingMarkup = renderToStaticMarkup(createElement(RouteLoading))
  assert.match(loadingMarkup, /role="status"/)
  assert.match(loadingMarkup, /checking available risk data/)

  const resultMarkup = renderToStaticMarkup(createElement(RouteDetails, { assessment }))
  assert.match(resultMarkup, /5\.4 km/)
  assert.match(resultMarkup, /15 min/)
  assert.match(resultMarkup, /HIGH RISK/)
  assert.match(resultMarkup, /Verified report near route/)
  assert.match(resultMarkup, /NOT ASSESSED/)
  assert.match(resultMarkup, /Road conditions can change quickly/)
  assert.match(resultMarkup, /Citizen-submitted; not an official road warning/)
  assert.match(resultMarkup, /Official SACHET alert/)
})

test('safe route API sends selected coordinates and returns provider assessment', async () => {
  let requestUrl = ''
  let options
  const result = await findSafeRoute(origin, destination, {
    fetchImpl: async (url, requestOptions) => {
      requestUrl = url
      options = requestOptions
      return { ok: true, json: async () => assessment }
    },
  })
  assert.match(requestUrl, /^http:\/\/127\.0\.0\.1:8000\/api\/routes\/safe-route\/$/)
  assert.equal(options.method, 'POST')
  assert.deepEqual(JSON.parse(options.body), {
    origin: { latitude: origin.latitude, longitude: origin.longitude },
    destination: { latitude: destination.latitude, longitude: destination.longitude },
  })
  assert.equal(result, assessment)
})

test('safe route API exposes server errors and connection failures', async () => {
  await assert.rejects(
    findSafeRoute(origin, destination, {
      fetchImpl: async () => ({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'OSRM could not provide a route.' }),
      }),
    }),
    /OSRM could not provide a route/,
  )
  await assert.rejects(
    findSafeRoute(origin, destination, {
      fetchImpl: async () => { throw new Error('offline') },
    }),
    /Cannot connect to the FLOODGUARD route service/,
  )
})

test('route layout adapts to the existing tablet and mobile breakpoints', () => {
  const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')
  const tabletRules = css.match(/@media \(max-width: 760px\) \{([\s\S]*?)\n\}/)?.[1] || ''
  const mobileRules = css.match(/@media \(max-width: 520px\) \{([\s\S]*?)\n\}/)?.[1] || ''
  assert.match(tabletRules, /\.route-layout[^}]*grid-template-columns: minmax\(0, 1fr\)/)
  assert.match(tabletRules, /\.route-map \{ height: 270px; \}/)
  assert.match(mobileRules, /\.route-map \{ height: 235px; \}/)
})
