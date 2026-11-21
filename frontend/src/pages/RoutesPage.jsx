import { Suspense, lazy, useEffect, useReducer, useRef, useState } from 'react'
import {
  ArrowLeftRight, CircleAlert, LoaderCircle, MapPin, Navigation, Route, ShieldAlert,
} from 'lucide-react'
import { DemoNotice, PageHeader, Panel, Pill } from '../components/UI'
import { RouteDetails, RouteLoading } from '../components/RouteDetails.js'
import 'leaflet/dist/leaflet.css'
import { searchWeatherLocations } from '../services/weatherApi'
import {
  findSafeRoute,
  getRouteFormError,
  initialRouteFinderState,
  routeFinderReducer,
} from '../services/safeRouteApi'

const RouteMap = lazy(() => import('../components/RouteMap'))

function LocationSearch({ label, value, onSelect, pointType, placeholder }) {
  const [query, setQuery] = useState(value?.name || '')
  const [results, setResults] = useState([])
  const [lookupStatus, setLookupStatus] = useState('idle')
  const [lookupError, setLookupError] = useState('')

  useEffect(() => {
    if (value) setQuery(value.name)
  }, [value?.latitude, value?.longitude, value?.name])

  useEffect(() => {
    if (value && query === value.name) {
      setResults([])
      setLookupStatus('idle')
      return undefined
    }
    if (query.trim().length < 2) {
      setResults([])
      setLookupStatus('idle')
      return undefined
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLookupStatus('loading')
      setLookupError('')
      searchWeatherLocations(query.trim(), { signal: controller.signal })
        .then((locations) => {
          setResults(locations)
          setLookupStatus(locations.length ? 'success' : 'empty')
        })
        .catch((error) => {
          if (error.name !== 'AbortError') {
            setResults([])
            setLookupStatus('error')
            setLookupError(error.message)
          }
        })
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, value])

  function updateQuery(nextQuery) {
    setQuery(nextQuery)
    if (value) onSelect(null)
  }

  return (
    <div className="route-location-field">
      <label className="route-input-label">
        <span className={`route-point route-point-${pointType}`} />
        <span>{label}</span>
        <input
          autoComplete="off"
          value={query}
          onChange={(event) => updateQuery(event.target.value)}
          placeholder={placeholder}
          role="combobox"
          aria-expanded={results.length > 0}
          aria-autocomplete="list"
          aria-controls={`route-results-${pointType}`}
        />
      </label>
      {lookupStatus === 'loading' && <span className="route-search-message">Searching Open-Meteo locations…</span>}
      {lookupStatus === 'empty' && <span className="route-search-message">No matching places found.</span>}
      {lookupStatus === 'error' && <span className="route-search-message route-search-error" role="status">{lookupError}</span>}
      {results.length > 0 && <div className="route-location-results" id={`route-results-${pointType}`} role="listbox" aria-label={`${label} search results`}>
        {results.map((location) => (
          <button
            className="route-location-result"
            key={`${location.latitude}-${location.longitude}`}
            type="button"
            role="option"
            aria-selected="false"
            onClick={() => {
              onSelect(location)
              setQuery(location.name)
              setResults([])
              setLookupStatus('idle')
            }}
          >
            <MapPin size={14} /><span><strong>{location.name}</strong><small>{[location.admin1, location.country].filter(Boolean).join(', ')}</small></span>
          </button>
        ))}
      </div>}
      {value && <span className="route-selected-place">Selected: {value.name} · {value.latitude.toFixed(4)}, {value.longitude.toFixed(4)}</span>}
    </div>
  )
}

export default function RoutesPage() {
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  const [finder, dispatch] = useReducer(routeFinderReducer, initialRouteFinderState)
  const [formError, setFormError] = useState('')
  const [locationError, setLocationError] = useState('')
  const [locating, setLocating] = useState(false)
  const requestController = useRef(null)

  useEffect(() => () => requestController.current?.abort(), [])

  function chooseOrigin(place) {
    requestController.current?.abort()
    setOrigin(place)
    setFormError('')
    dispatch({ type: 'reset' })
  }

  function chooseDestination(place) {
    requestController.current?.abort()
    setDestination(place)
    setFormError('')
    dispatch({ type: 'reset' })
  }

  function useCurrentLocation() {
    setLocationError('')
    if (!navigator.geolocation) {
      setLocationError('This browser does not support location access. Search for a starting place instead.')
      return
    }

    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        chooseOrigin({
          name: 'Current location',
          latitude: coords.latitude,
          longitude: coords.longitude,
        })
        setLocating(false)
      },
      (error) => {
        setLocating(false)
        setLocationError(
          error.code === error.PERMISSION_DENIED
            ? 'Location permission was not granted. Search for a starting place instead.'
            : 'Could not retrieve your location. Search for a starting place instead.',
        )
      },
      { enableHighAccuracy: false, maximumAge: 0, timeout: 10000 },
    )
  }

  async function submitRoute(event) {
    event.preventDefault()
    const validationError = getRouteFormError(origin, destination)
    if (validationError) {
      setFormError(validationError)
      dispatch({ type: 'reset' })
      return
    }
    setFormError('')
    dispatch({ type: 'start' })
    const controller = new AbortController()
    requestController.current?.abort()
    requestController.current = controller
    try {
      const assessment = await findSafeRoute(origin, destination, { signal: controller.signal })
      dispatch({ type: 'success', route: assessment })
    } catch (error) {
      if (error.name !== 'AbortError') dispatch({ type: 'failure', error: error.message })
    } finally {
      if (requestController.current === controller) requestController.current = null
    }
  }

  function swapLocations() {
    requestController.current?.abort()
    setOrigin(destination)
    setDestination(origin)
    setFormError('')
    dispatch({ type: 'reset' })
  }

  const status = formError ? 'error' : finder.status

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="MOBILITY & ACCESS"
        title="Safe route finder"
        description="Review an OSRM road route alongside citizen flood reports, official SACHET alerts and weather indicators."
      />
      <DemoNotice>
        Routes are based on available road-routing data and reported flood information. Road closures, live flood depth and actual road safety are not guaranteed. Follow official authorities and local emergency instructions.
      </DemoNotice>
      <div className="route-layout">
        <Panel className="route-form-panel" title="Plan a journey" subtitle="Search for a place or choose current location with permission">
          <form className="route-form" onSubmit={submitRoute} noValidate>
            <LocationSearch
              label="Starting point"
              pointType="start"
              value={origin}
              onSelect={chooseOrigin}
              placeholder="Search a city or place"
            />
            <div className="route-connector">
              <span />
              <button type="button" className="swap-button" aria-label="Swap starting point and destination" onClick={swapLocations}>
                <ArrowLeftRight size={15} />
              </button>
            </div>
            <LocationSearch
              label="Destination"
              pointType="end"
              value={destination}
              onSelect={chooseDestination}
              placeholder="Search a city or place"
            />
            <button className="secondary-button route-geolocation" type="button" onClick={useCurrentLocation} disabled={locating}>
              {locating ? <LoaderCircle size={15} className="weather-spin" /> : <Navigation size={15} />}
              {locating ? 'Requesting location…' : 'Use my current location'}
            </button>
            {locationError && <p className="route-form-error" role="alert">{locationError}</p>}
            <button className="primary-button route-submit" type="submit" disabled={finder.status === 'loading'}>
              <Route size={16} />{finder.status === 'loading' ? 'Finding route…' : 'Find safe route'}
            </button>
          </form>
          {(formError || finder.status === 'error') && <div className="inline-feedback route-error" role="alert">
            <CircleAlert size={16} />{formError || finder.error}
          </div>}
          {finder.status === 'loading' && <RouteLoading />}
          <div className="route-safety-note"><ShieldAlert size={17} /><span>Route safety cannot be guaranteed. No flood reports does not mean a road is safe; follow official instructions.</span></div>
        </Panel>

        <Panel
          className="route-map-panel"
          title={finder.status === 'success' ? 'Route map' : 'Route preview'}
          subtitle={finder.status === 'success' ? 'OpenStreetMap tiles · OSRM driving geometry' : 'A route map appears after a successful route request'}
          action={<Pill tone={finder.status === 'success' ? 'teal' : 'neutral'}>{finder.status === 'success' ? 'OSM · OSRM' : 'AWAITING ROUTE'}</Pill>}
        >
          {finder.route
            ? <Suspense fallback={<RouteLoading />}><RouteMap assessment={finder.route} /></Suspense>
            : <div className="route-map-placeholder"><MapPin size={30} /><strong>No route preview yet</strong><span>Select locations and request a route. No coordinates or roads are guessed.</span></div>}
          <div className="route-legend">
            <span><i className="route-legend-line" /> OSRM route</span>
            <span><i className="route-legend-dot route-legend-high" /> Verified citizen report</span>
            <span><i className="route-legend-dot route-legend-pending" /> Pending citizen report</span>
            <span><i className="route-legend-dot route-legend-official" /> Official SACHET alert</span>
            <span><i className="route-legend-dot route-legend-low" /> Weather indicator</span>
          </div>
          <p className="route-provider-caption">Road geometry and travel estimates: OSRM / OpenStreetMap. Map tiles: Leaflet + OpenStreetMap. Weather indicators: Open-Meteo. Official alerts: NDMA SACHET. Public routing and tile services may have usage limits and do not provide live road-closure verification.</p>
        </Panel>
      </div>

      {finder.route && <>
        <RouteDetails assessment={finder.route} />
        {finder.route.history?.status === 'unavailable' && <div className="route-history-warning" role="status">
          <CircleAlert size={16} /><span>{finder.route.history.detail}</span>
        </div>}
      </>}

      <div className="notice-strip"><ShieldAlert size={17} /><div><strong>Safety disclaimer</strong><span>Routes are based on available road-routing data and reported flood information. Road closures, live flood depth and actual road safety are not guaranteed. Follow official authorities and local emergency instructions.</span></div></div>
    </div>
  )
}
