import { useEffect, useState } from 'react'
import { ExternalLink, Radio, Search, ShieldAlert } from 'lucide-react'
import {
  EmptyEmergencyState,
  AlertCard,
  SachetFeedStatus,
} from '../components/EmergencyCards'
import { PageHeader, Panel } from '../components/UI'
import { officialEmergencySources } from '../data/officialEmergencySources'
import {
  getAlertClientId,
  getSachetFeed,
  listAlerts,
  markAlertRead,
} from '../services/emergencyApi'

const severities = ['Information', 'Advisory', 'Warning', 'Emergency']

export default function AlertsPage() {
  const [clientId] = useState(getAlertClientId)
  const [page, setPage] = useState(null)
  const [sachetFeed, setSachetFeed] = useState({
    data: null,
    error: '',
    loading: true,
  })
  const [severity, setSeverity] = useState('')
  const [district, setDistrict] = useState('')
  const [query, setQuery] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [readError, setReadError] = useState('')
  const [pendingRead, setPendingRead] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getSachetFeed({ signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setSachetFeed({ data, error: '', loading: false })
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted && cause.name !== 'AbortError') {
          setSachetFeed({ data: null, error: cause.message, loading: false })
        }
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setPage(null)
    listAlerts({ severity, district, search: query, source_type: sourceType, client_id: clientId, limit: 20, offset }, { signal: controller.signal })
      .then(setPage)
      .catch((cause) => {
        if (cause.name !== 'AbortError') setError(cause.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [clientId, severity, district, query, sourceType, offset])

  async function handleMarkRead(alertId) {
    setPendingRead(alertId)
    setReadError('')
    try {
      await markAlertRead(alertId, clientId)
      setPage((current) => current && ({
        ...current,
        unread_count: Math.max(0, current.unread_count - (current.results.some((item) => item.alert_id === alertId && !item.is_read) ? 1 : 0)),
        results: current.results.map((item) => item.alert_id === alertId ? { ...item, is_read: true } : item),
      }))
    } catch (cause) {
      setReadError(cause.message)
    } finally {
      setPendingRead('')
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SITUATIONAL AWARENESS"
        title="Flood alerts"
        description="Official SACHET feed entries, stored notices, verified community reports, and explicitly labelled weather advisories."
        action={<span className="updated-chip"><Radio size={14} /> {error ? 'UNAVAILABLE' : loading ? '… UNREAD' : `${page?.unread_count ?? 0} UNREAD`}</span>}
      />

      <Panel
        className="sachet-feed-panel"
        title="Official SACHET feed entries · Odisha"
        subtitle="Retrieved by the FLOODGUARD backend from the NDMA RSS feed. Feed entries are not confirmation that an alert remains valid."
      >
        <SachetFeedStatus
          feed={sachetFeed.data}
          loading={sachetFeed.loading}
          error={sachetFeed.error}
        />
        {!sachetFeed.loading && !sachetFeed.error && sachetFeed.data?.alerts.length === 0 && sachetFeed.data.status === 'empty' && (
          <EmptyEmergencyState
            title="No unexpired SACHET feed entries"
            description="The RSS feed was checked, but this does not establish that no flood or other hazard exists. Check the official portal."
          />
        )}
        {!sachetFeed.loading && !sachetFeed.error && sachetFeed.data?.alerts.length > 0 && (
          <div className="emergency-alert-list" aria-live="polite">
            {sachetFeed.data.alerts.map((alert) => (
              <AlertCard key={alert.alert_id} alert={alert} />
            ))}
          </div>
        )}
      </Panel>

      <Panel className="alerts-directory" title="Active alerts" subtitle={loading ? 'Refreshing active records…' : error ? 'Active records unavailable' : `${page?.count ?? 0} active records · source labels and publication timestamps are shown where available`}>
        <div className="emergency-filter-grid alert-filter-grid">
          <label className="search-field">
            <Search size={16} /><span className="sr-only">Search alerts</span>
            <input value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0) }} placeholder="Search title or location" />
          </label>
          <label className="sr-only" htmlFor="alert-severity">Filter by alert severity</label>
          <select id="alert-severity" className="emergency-filter-select" value={severity} onChange={(event) => { setSeverity(event.target.value); setOffset(0) }}>
            <option value="">All severities</option>
            {severities.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <label className="sr-only" htmlFor="alert-source">Filter by source</label>
          <select id="alert-source" className="emergency-filter-select" value={sourceType} onChange={(event) => { setSourceType(event.target.value); setOffset(0) }}>
            <option value="">All sources</option>
            <option value="official">Official</option>
            <option value="manual">Staff-managed</option>
            <option value="weather">Weather-based</option>
            <option value="community">Verified community reports</option>
          </select>
          <label className="sr-only" htmlFor="alert-district">Filter by district</label>
          <input id="alert-district" className="emergency-filter-select" value={district} onChange={(event) => { setDistrict(event.target.value); setOffset(0) }} placeholder="District" />
        </div>

        {readError && <p className="emergency-inline-error" role="alert">Read status was not saved: {readError}</p>}
        {error && <EmptyEmergencyState error title="Alerts unavailable" description={error} />}
        {!error && loading && <EmptyEmergencyState loading title="Loading active alerts" description="Checking current backend records and available advisory sources…" />}
        {!error && !loading && page?.results.length === 0 && (
          <EmptyEmergencyState
            title={severity || district || query || sourceType ? 'No alerts match these filters' : 'No active alerts available'}
            description={severity || district || query || sourceType
              ? 'Try adjusting the filters. No alert has been generated to fill an empty result.'
              : 'No other active FLOODGUARD alert records are currently stored. SACHET feed status is shown separately above; check official channels for current instructions.'}
          />
        )}
        {!error && page?.results.length > 0 && (
          <div className="emergency-alert-list" aria-live="polite">
            {page.results.map((alert) => (
              <div className={pendingRead === alert.alert_id ? 'emergency-alert-pending' : ''} key={alert.alert_id}>
                <AlertCard alert={alert} onMarkRead={!alert.is_read ? handleMarkRead : undefined} />
              </div>
            ))}
          </div>
        )}
        {!error && page && page.count > 20 && (
          <div className="emergency-pagination">
            <button type="button" className="secondary-button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button>
            <span>Showing {offset + 1}–{offset + page.results.length} of {page.count}</span>
            <button type="button" className="secondary-button" disabled={page.next_offset === null || loading} onClick={() => setOffset(page.next_offset)}>Next</button>
          </div>
        )}
      </Panel>

      <Panel title="Official alert sources" subtitle="The Odisha SACHET RSS feed is checked through Django; the other links are references only.">
        <div className="alert-source-links">
          {officialEmergencySources.filter((source) => source.id === 'osdma-contacts' || source.id === 'src-odisha' || source.id === 'odisha-directory' || source.id === 'sachet-alerts').map((source) => (
            <a key={source.id} href={source.url} target="_blank" rel="noreferrer">
              <span><strong>{source.title}</strong><small>{source.status}</small></span><ExternalLink size={14} />
            </a>
          ))}
        </div>
        <p className="emergency-source-status">
          Weather source: {page?.sources?.weather || 'not requested'} · Verified report source: {page?.sources?.verified_reports || 'unknown'}.
          {' '}Weather advisories are not official warnings. FLOODGUARD does not provide guaranteed emergency notifications or contact responders.
        </p>
      </Panel>
      <div className="page-footnote"><ShieldAlert size={16} /> Route suggestions and alerts are informational and may not reflect current road closures or rapidly changing flood conditions. Follow official evacuation instructions and avoid entering floodwater.</div>
    </div>
  )
}
