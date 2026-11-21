const API_BASE = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

async function requestJson(url, options, serviceName = 'Weather') {
  let response
  try {
    response = await fetch(url, options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error(`Cannot connect to the FLOODGUARD ${serviceName.toLowerCase()} service.`)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok && !body?.weather) {
    throw new Error(body?.detail || `${serviceName} service returned HTTP ${response.status}.`)
  }
  return { body, status: response.status }
}

export async function searchWeatherLocations(query, options = {}) {
  const params = new URLSearchParams({ q: query })
  const { body } = await requestJson(`${API_BASE}/api/weather/locations/?${params}`, options)
  return body.results
}

export async function fetchWeather(location, options = {}) {
  const params = new URLSearchParams({
    latitude: String(location.latitude),
    longitude: String(location.longitude),
    location_name: location.name,
  })
  if (location.timezone) params.set('timezone', location.timezone)
  const { body, status } = await requestJson(`${API_BASE}/api/weather/?${params}`, options)
  if (body.weather) return { weather: body.weather, storageError: body.detail }
  return { weather: body, storageError: null, httpStatus: status }
}

export async function assessFloodRisk(location, options = {}) {
  const params = new URLSearchParams({
    latitude: String(location.latitude),
    longitude: String(location.longitude),
    location: location.name,
  })
  if (location.timezone) params.set('timezone', location.timezone)
  const { body } = await requestJson(`${API_BASE}/api/risk/assess/?${params}`, options, 'Risk assessment')
  return body
}
