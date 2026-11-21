const API_BASE = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export function getRouteFormError(origin, destination) {
  for (const [label, point] of [['starting point', origin], ['destination', destination]]) {
    if (!point) return `Search for and select a valid ${label}.`
    if (
      !Number.isFinite(point.latitude)
      || !Number.isFinite(point.longitude)
      || point.latitude < -90
      || point.latitude > 90
      || point.longitude < -180
      || point.longitude > 180
    ) {
      return `The selected ${label} has invalid coordinates.`
    }
  }
  if (origin.latitude === destination.latitude && origin.longitude === destination.longitude) {
    return 'Choose a destination different from the starting point.'
  }
  return ''
}

export function routeFinderReducer(state, action) {
  switch (action.type) {
    case 'start':
      return { status: 'loading', route: null, error: '' }
    case 'success':
      return { status: 'success', route: action.route, error: '' }
    case 'failure':
      return { status: 'error', route: null, error: action.error }
    case 'reset':
      return { status: 'idle', route: null, error: '' }
    default:
      return state
  }
}

export const initialRouteFinderState = { status: 'idle', route: null, error: '' }

export async function findSafeRoute(origin, destination, { signal, fetchImpl = fetch } = {}) {
  const validationError = getRouteFormError(origin, destination)
  if (validationError) throw new Error(validationError)

  let response
  try {
    response = await fetchImpl(`${API_BASE}/api/routes/safe-route/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin: { latitude: origin.latitude, longitude: origin.longitude },
        destination: { latitude: destination.latitude, longitude: destination.longitude },
      }),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot connect to the FLOODGUARD route service.')
  }

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.detail || `Route service returned HTTP ${response.status}.`)
  }
  if (!body?.route?.geometry?.coordinates || !body?.risk_classification?.level) {
    throw new Error('The route service returned an incomplete assessment.')
  }
  return body
}
