import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, Bell, Bot, ChevronDown, CircleHelp, Droplets, House,
  MapPinned, Menu, Route, Search, Settings, ShieldAlert, X, MapPin, Siren,
} from 'lucide-react'
import { searchWeatherLocations } from '../services/weatherApi'
import { getAlertClientId, listAlerts, markAlertRead } from '../services/emergencyApi'

const navigation = [
  { to: '/', label: 'Overview', icon: House, end: true },
  { to: '/resources', label: 'Emergency Resources', icon: Droplets },
  { to: '/alerts', label: 'Flood Alerts', icon: Siren },
  { to: '/reports', label: 'Flood Reports', icon: ShieldAlert },
  { to: '/routes', label: 'Safe Route Finder', icon: Route },
  { to: '/risk', label: 'AI Flood Risk', icon: Activity },
  { to: '/assistant', label: 'AI Emergency Assistant', icon: Bot },
]

export default function AppShell() {
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [locationSearchOpen, setLocationSearchOpen] = useState(false)
  const [locationQuery, setLocationQuery] = useState('')
  const [locationResults, setLocationResults] = useState([])
  const [locationLookup, setLocationLookup] = useState('idle')
  const [locationLookupError, setLocationLookupError] = useState('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [noticeOpen, setNoticeOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [apiStatus, setApiStatus] = useState('checking')
  const [alertClientId] = useState(getAlertClientId)
  const [noticePage, setNoticePage] = useState({ results: [], unread_count: 0 })
  const [noticeLoading, setNoticeLoading] = useState(false)
  const [noticeError, setNoticeError] = useState('')
  const [noticePending, setNoticePending] = useState('')
  const navigate = useNavigate()
  const routeLocation = useLocation()

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/health/`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('API unavailable')))
      .then((data) => setApiStatus(data.status === 'ok' ? 'online' : 'offline'))
      .catch((error) => {
        if (error.name !== 'AbortError') setApiStatus('offline')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setNoticeLoading(true)
    setNoticeError('')
    setNoticePage({ results: [], unread_count: 0 })
    listAlerts({
      client_id: alertClientId,
      latitude: selectedLocation?.latitude,
      longitude: selectedLocation?.longitude,
      location_name: selectedLocation?.name,
      limit: 5,
      offset: 0,
    }, { signal: controller.signal })
      .then(setNoticePage)
      .catch((error) => {
        if (error.name !== 'AbortError') setNoticeError(error.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setNoticeLoading(false)
      })
    return () => controller.abort()
  }, [alertClientId, selectedLocation])

  useEffect(() => {
    const controller = new AbortController()
    searchWeatherLocations('Bhubaneswar', { signal: controller.signal })
      .then((results) => { if (results[0]) setSelectedLocation(results[0]) })
      .catch((error) => {
        if (error.name !== 'AbortError') setLocationLookupError('Search for a location to load weather.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!locationSearchOpen) return undefined
    const query = locationQuery.trim()
    if (query.length < 2) {
      setLocationResults([])
      setLocationLookup(query ? 'invalid' : 'idle')
      setLocationLookupError(query ? 'Enter at least 2 characters.' : '')
      return undefined
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLocationLookup('loading')
      setLocationLookupError('')
      searchWeatherLocations(query, { signal: controller.signal })
        .then((results) => {
          setLocationResults(results)
          setLocationLookup(results.length ? 'success' : 'empty')
        })
        .catch((error) => {
          if (error.name !== 'AbortError') {
            setLocationResults([])
            setLocationLookup('error')
            setLocationLookupError(error.message)
          }
        })
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [locationQuery, locationSearchOpen])

  function closeMenus() {
    setMobileNavOpen(false)
    setNoticeOpen(false)
    setProfileOpen(false)
  }

  async function markNoticeRead(alertId) {
    setNoticePending(alertId)
    setNoticeError('')
    try {
      await markAlertRead(alertId, alertClientId)
      setNoticePage((current) => ({
        ...current,
        unread_count: Math.max(0, current.unread_count - (current.results.some((item) => item.alert_id === alertId && !item.is_read) ? 1 : 0)),
        results: current.results.map((item) => item.alert_id === alertId ? { ...item, is_read: true } : item),
      }))
    } catch (error) {
      setNoticeError(error.message)
    } finally {
      setNoticePending('')
    }
  }

  return (
    <div className="app-frame">
      {mobileNavOpen && <button className="mobile-scrim" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation" />}
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <span className="brand-symbol"><Droplets size={20} strokeWidth={2.2} /></span>
          <span className="brand-wordmark">FLOODGUARD <b>AI</b></span>
          <button className="icon-button mobile-close" onClick={() => setMobileNavOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={closeMenus} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <NavLink to="/settings" onClick={closeMenus} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}>
            <Settings size={18} strokeWidth={1.8} /><span>Settings</span>
          </NavLink>
          <div className="sidebar-help">
            <div className="help-icon"><CircleHelp size={17} /></div>
            <div><strong>Need assistance?</strong><span>Emergency support links</span></div>
            <button className="help-open" aria-label="Open emergency assistant" onClick={() => navigate('/assistant')}><ChevronDown size={16} /></button>
          </div>
          <div className="sidebar-footnote"><span className="status-led" /> DEMONSTRATION ENVIRONMENT</div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{currentSection(routeLocation.pathname)}</strong></div>
          </div>
          <div className="topbar-actions">
            <div className="popover-anchor location-anchor">
              <button className="location-control" onClick={() => { setLocationSearchOpen(!locationSearchOpen); setLocationQuery(''); setLocationLookupError(''); setNoticeOpen(false); setProfileOpen(false) }} aria-label="Select weather location" aria-expanded={locationSearchOpen}>
                <MapPinned size={16} />
                <span>{selectedLocation ? selectedLocation.name : locationLookupError ? 'Choose location' : 'Finding Bhubaneswar…'}</span>
                <ChevronDown size={14} className="select-chevron" />
              </button>
              {locationSearchOpen && <div className="popover location-popover" onClick={(event) => event.stopPropagation()}>
                <div className="location-popover-heading"><strong>Choose a location</strong><button className="icon-button" onClick={() => setLocationSearchOpen(false)} aria-label="Close location search"><X size={15} /></button></div>
                <label className="location-search"><Search size={15} /><span className="sr-only">Search places</span><input autoFocus value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="City, region, or postal code" /></label>
                <div className="location-results" aria-live="polite">
                  {locationLookup === 'loading' && <span className="location-search-message">Searching locations…</span>}
                  {locationLookup === 'idle' && <span className="location-search-message">Type at least 2 characters to search.</span>}
                  {locationLookup === 'invalid' && <span className="location-search-message">{locationLookupError}</span>}
                  {locationLookup === 'empty' && <span className="location-search-message">No matching locations found.</span>}
                  {locationLookup === 'error' && <span className="location-search-message location-search-error">{locationLookupError}</span>}
                  {locationResults.map((result, index) => <button className="location-result" key={`${result.latitude}-${result.longitude}-${index}`} onClick={() => { setSelectedLocation(result); setLocationSearchOpen(false); setLocationResults([]) }}>
                    <MapPin size={15} /><span><strong>{result.name}</strong><small>{[result.admin1, result.country].filter(Boolean).join(', ')}</small></span>
                  </button>)}
                </div>
                <div className="location-popover-footer"><span>Location data: Open-Meteo Geocoding</span>{selectedLocation && <button className="text-button" onClick={() => { setSelectedLocation(null); setLocationSearchOpen(false) }}>Clear selection</button>}</div>
              </div>}
            </div>

            <div className="popover-anchor">
              <button className={`icon-button top-action ${noticeOpen ? 'icon-button-selected' : ''}`} onClick={() => { setNoticeOpen(!noticeOpen); setProfileOpen(false) }} aria-label={`Notifications${noticePage.unread_count > 0 ? `, ${noticePage.unread_count} unread` : ''}`} aria-expanded={noticeOpen}>
                <Bell size={18} />
                {noticePage.unread_count > 0 && <span className="notification-count">{noticePage.unread_count > 99 ? '99+' : noticePage.unread_count}</span>}
              </button>
              {noticeOpen && <div className="popover notification-popover">
                <div className="popover-title"><strong>Alerts</strong><span className="notification-unread-label">{noticePage.unread_count} unread</span></div>
                {noticeError && <p className="notification-error" role="alert">Alerts unavailable: {noticeError}</p>}
                {!noticeError && noticeLoading && <p className="notification-state" role="status">Loading current alerts…</p>}
                {!noticeError && !noticeLoading && noticePage.results.length === 0 && <p className="notification-state">No active alerts available.</p>}
                {!noticeError && !noticeLoading && noticePage.results.map((alert) => (
                  <div className={`notification-item${alert.is_read ? ' notification-item-read' : ''}`} key={alert.alert_id}>
                    <span className={`alert-marker alert-marker-${alert.severity.toLowerCase()}`} />
                    <div>
                      <Link to={`/alerts/${encodeURIComponent(alert.alert_id)}`} onClick={closeMenus}><strong>{alert.title}</strong></Link>
                      <span>{alert.affected_location} · {alert.source_name}</span>
                      <small>{alert.source_published_at ? new Date(alert.source_published_at).toLocaleString() : 'Publication time unavailable'}</small>
                      {!alert.is_read && <button className="text-button notification-mark-read" disabled={noticePending === alert.alert_id} onClick={() => markNoticeRead(alert.alert_id)}>{noticePending === alert.alert_id ? 'Saving…' : 'Mark as read'}</button>}
                    </div>
                  </div>
                ))}
                <Link className="inline-link notification-view-all" to="/alerts" onClick={closeMenus}>View all alerts <Siren size={13} /></Link>
                <p className="popover-disclaimer">Alerts are informational and may not reflect rapidly changing conditions. Follow official instructions.</p>
              </div>}
            </div>

            <div className="popover-anchor profile-anchor">
              <button className="profile-button" onClick={() => { setProfileOpen(!profileOpen); setNoticeOpen(false) }} aria-expanded={profileOpen}>
                <span className="avatar">FG</span><span className="profile-copy"><strong>Field Operations</strong><small>Demo account</small></span><ChevronDown size={15} />
              </button>
              {profileOpen && <div className="popover profile-popover"><div className="profile-menu-heading"><strong>Demo workspace</strong><small>No account is connected</small></div><button className="profile-menu-link" onClick={() => { closeMenus(); navigate('/settings') }}><Settings size={15} /> Preferences</button></div>}
            </div>
          </div>
        </header>
        <main className="content-area" onClick={() => { if (noticeOpen || profileOpen) { setNoticeOpen(false); setProfileOpen(false) } }}>
          <Outlet context={{ location: selectedLocation?.name || null, selectedLocation, apiStatus }} />
        </main>
        <footer className="app-footer"><span>FLOODGUARD AI <span className="footer-dot">·</span> Predict. Prepare. Protect.</span><span><span className={`api-led api-${apiStatus}`} /> API {apiStatus}</span></footer>
      </div>
    </div>
  )
}

function currentSection(pathname) {
  const match = navigation.find(({ to }) => to !== '/' && pathname.startsWith(to))
  if (match) return match.label
  if (pathname === '/settings') return 'Settings'
  return 'Overview'
}
