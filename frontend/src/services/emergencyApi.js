const API_BASE = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const CLIENT_ID_KEY = 'floodguard-alert-client-id'
let sessionClientId = ''

function messageFrom(body, fallback) {
  if (typeof body?.detail === 'string') return body.detail
  if (body && typeof body === 'object') {
    return Object.entries(body)
      .map(([field, messages]) => `${field}: ${Array.isArray(messages) ? messages.join(' ') : messages}`)
      .join(' ')
  }
  return fallback
}

async function requestJson(path, options = {}, fetchImpl = fetch) {
  let response
  try {
    response = await fetchImpl(`${API_BASE}${path}`, options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot connect to the FLOODGUARD emergency information service.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(messageFrom(body, `Emergency information service returned HTTP ${response.status}.`))
  }
  return body
}

function createClientId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  return [...bytes].map((byte, index) => {
    const text = byte.toString(16).padStart(2, '0')
    return [4, 6, 8, 10].includes(index) ? `-${text}` : text
  }).join('')
}

export function getAlertClientId() {
  if (typeof window === 'undefined') return ''
  try {
    const stored = window.localStorage.getItem(CLIENT_ID_KEY)
    if (stored && /^[0-9a-f-]{36}$/i.test(stored)) return stored
    const clientId = createClientId()
    window.localStorage.setItem(CLIENT_ID_KEY, clientId)
    return clientId
  } catch (error) {
    if (error?.name !== 'SecurityError' && error?.name !== 'QuotaExceededError') throw error
    if (!sessionClientId) sessionClientId = createClientId()
    return sessionClientId
  }
}

export function listResources(filters = {}, { signal, fetchImpl } = {}) {
  const params = new URLSearchParams()
  for (const key of ['category', 'district', 'search', 'verification_status', 'is_active', 'limit', 'offset']) {
    if (filters[key] !== undefined && filters[key] !== null && filters[key] !== '') {
      params.set(key, String(filters[key]))
    }
  }
  return requestJson(`/api/resources/?${params}`, { signal }, fetchImpl)
}

export function listResourceCategories({ signal, fetchImpl } = {}) {
  return requestJson('/api/resources/categories/', { signal }, fetchImpl)
}

export function getResource(resourceId, { signal, fetchImpl } = {}) {
  return requestJson(`/api/resources/${encodeURIComponent(resourceId)}/`, { signal }, fetchImpl)
}

export function listAlerts(filters = {}, { signal, fetchImpl } = {}) {
  const params = new URLSearchParams()
  for (const key of ['severity', 'district', 'search', 'source_type', 'verification_status', 'latitude', 'longitude', 'location_name', 'limit', 'offset']) {
    if (filters[key] !== undefined && filters[key] !== null && filters[key] !== '') {
      params.set(key, String(filters[key]))
    }
  }
  if (filters.client_id) params.set('client_id', filters.client_id)
  return requestJson(`/api/alerts/?${params}`, { signal }, fetchImpl)
}

export function getSachetFeed({ signal, fetchImpl } = {}) {
  return requestJson('/api/alerts/sachet/', { signal }, fetchImpl)
}

export function getAlert(alertId, clientId, { signal, fetchImpl } = {}) {
  const params = new URLSearchParams()
  if (clientId) params.set('client_id', clientId)
  const suffix = params.size ? `?${params}` : ''
  return requestJson(`/api/alerts/${encodeURIComponent(alertId)}/${suffix}`, { signal }, fetchImpl)
}

export function markAlertRead(alertId, clientId, { signal, fetchImpl } = {}) {
  return requestJson('/api/alerts/mark-read/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_id: alertId, client_id: clientId }),
    signal,
  }, fetchImpl)
}

export function listVerifiedReports({ limit = 3, signal, fetchImpl } = {}) {
  const params = new URLSearchParams({
    status: 'verified',
    limit: String(limit),
    offset: '0',
  })
  return requestJson(`/api/reports/?${params}`, { signal }, fetchImpl)
}
