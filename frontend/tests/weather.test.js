import assert from 'node:assert/strict'
import test from 'node:test'
import { getWeatherCondition } from '../src/data/weatherConditions.js'
import { assessFloodRisk, fetchWeather, searchWeatherLocations } from '../src/services/weatherApi.js'
import { createWeatherState, weatherStateReducer } from '../src/services/weatherState.js'

test('condition mapping covers common Open-Meteo WMO codes', () => {
  assert.equal(getWeatherCondition(0).description, 'Clear sky')
  assert.equal(getWeatherCondition(2).description, 'Partly cloudy')
  assert.equal(getWeatherCondition(45).description, 'Fog')
  assert.equal(getWeatherCondition(61).description, 'Slight rain')
  assert.equal(getWeatherCondition(71).description, 'Slight snow')
  assert.equal(getWeatherCondition(80).description, 'Slight rain showers')
  assert.equal(getWeatherCondition(95).description, 'Thunderstorm')
  assert.equal(getWeatherCondition(999).description, 'Condition unavailable')
})

test('weather request states cover no selection, loading, success, unavailable, and stale', () => {
  const empty = createWeatherState(false)
  assert.equal(empty.status, 'empty')

  const loading = createWeatherState(true)
  assert.equal(loading.status, 'loading')
  assert.equal(loading.weather, null)

  const providerResponse = { current: { values: { temperature_2m: 22 } } }
  const success = weatherStateReducer(loading, { type: 'success', weather: providerResponse })
  assert.equal(success.status, 'success')
  assert.equal(success.weather, providerResponse)

  const unavailable = weatherStateReducer(loading, { type: 'failure', message: 'Provider unavailable', keepWeather: false })
  assert.equal(unavailable.status, 'unavailable')
  assert.equal(unavailable.weather, null)
  assert.equal(unavailable.error, 'Provider unavailable')

  const stale = weatherStateReducer(success, { type: 'failure', message: 'Refresh failed', keepWeather: true })
  assert.equal(stale.status, 'stale')
  assert.equal(stale.weather, providerResponse)
  assert.equal(stale.error, 'Refresh failed')
})

test('changing locations clears prior weather instead of reusing stale location data', () => {
  const success = weatherStateReducer(createWeatherState(true), {
    type: 'success', weather: { location: { name: 'Bhubaneswar' } },
  })
  const changed = weatherStateReducer(success, { type: 'location_changed', locationSelected: true })
  assert.equal(changed.status, 'loading')
  assert.equal(changed.weather, null)
})

test('weather API client uses the Django endpoint and selected coordinates', async () => {
  const previousFetch = globalThis.fetch
  const providerWeather = { location: { latitude: 20.3 }, snapshot: { status: 'stored' } }
  let requestedUrl = ''
  globalThis.fetch = async (url) => {
    requestedUrl = url
    return { ok: true, status: 200, json: async () => providerWeather }
  }
  try {
    const result = await fetchWeather({ latitude: 20.2961, longitude: 85.8245, name: 'Bhubaneswar', timezone: 'Asia/Kolkata' })
    assert.match(requestedUrl, /^http:\/\/127\.0\.0\.1:8000\/api\/weather\//)
    assert.match(requestedUrl, /latitude=20\.2961/)
    assert.match(requestedUrl, /longitude=85\.8245/)
    assert.match(requestedUrl, /timezone=Asia%2FKolkata/)
    assert.equal(result.weather, providerWeather)
    assert.equal(result.storageError, null)
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('weather API client retains real provider data and reports storage failure', async () => {
  const previousFetch = globalThis.fetch
  const providerWeather = { current: { time: '2026-11-19T11:00' } }
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ weather: providerWeather, detail: 'Snapshot was not saved.' }),
  })
  try {
    const result = await fetchWeather({ latitude: 20, longitude: 85, name: 'Bhubaneswar' })
    assert.equal(result.weather, providerWeather)
    assert.equal(result.storageError, 'Snapshot was not saved.')
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('location search client calls the backend geocoding endpoint', async () => {
  const previousFetch = globalThis.fetch
  const locations = [{ name: 'Puri', latitude: 19.8, longitude: 85.8 }]
  let requestedUrl = ''
  globalThis.fetch = async (url) => {
    requestedUrl = url
    return { ok: true, status: 200, json: async () => ({ results: locations }) }
  }
  try {
    assert.deepEqual(await searchWeatherLocations('Puri'), locations)
    assert.match(requestedUrl, /\/api\/weather\/locations\/\?q=Puri$/)
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('risk assessment client sends the selected location to the Django endpoint', async () => {
  const previousFetch = globalThis.fetch
  const assessment = { score: 38, risk_level: 'Moderate' }
  let requestedUrl = ''
  globalThis.fetch = async (url) => {
    requestedUrl = url
    return { ok: true, status: 200, json: async () => assessment }
  }
  try {
    const result = await assessFloodRisk({
      latitude: 20.2961,
      longitude: 85.8245,
      name: 'Bhubaneswar',
      timezone: 'Asia/Kolkata',
    })
    assert.match(requestedUrl, /^http:\/\/127\.0\.0\.1:8000\/api\/risk\/assess\//)
    assert.match(requestedUrl, /latitude=20\.2961/)
    assert.match(requestedUrl, /longitude=85\.8245/)
    assert.match(requestedUrl, /location=Bhubaneswar/)
    assert.match(requestedUrl, /timezone=Asia%2FKolkata/)
    assert.equal(result, assessment)
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('risk assessment client exposes provider errors instead of fabricating a result', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    ok: false,
    status: 502,
    json: async () => ({ error: 'weather_provider_unavailable', detail: 'Open-Meteo unavailable.' }),
  })
  try {
    await assert.rejects(
      assessFloodRisk({ latitude: 20, longitude: 85, name: 'Test location' }),
      /Open-Meteo unavailable/,
    )
  } finally {
    globalThis.fetch = previousFetch
  }
})
