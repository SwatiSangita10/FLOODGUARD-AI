import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import {
  ArrowRight, CloudRain, Droplets, MapPin, Radio, ShieldAlert,
} from 'lucide-react'
import { AlertCard, EmptyEmergencyState, ResourceCard } from '../components/EmergencyCards'
import { PageHeader, Panel, Pill } from '../components/UI'
import WeatherPanel from '../components/WeatherPanel'
import { getAlertClientId, listAlerts, listResources, listVerifiedReports } from '../services/emergencyApi'
import { assessFloodRisk } from '../services/weatherApi'

const initialState = {
  alerts: { data: null, error: '' },
  reports: { data: null, error: '' },
  resources: { data: null, error: '' },
  risk: { data: null, error: '' },
}

function metricValue(value, loading, error) {
  if (error) return '—'
  if (loading) return '…'
  return value ?? '—'
}

export default function OverviewPage() {
  const { location, selectedLocation } = useOutletContext()
  const [clientId] = useState(getAlertClientId)
  const [data, setData] = useState(initialState)
  const [loading, setLoading] = useState(true)
  const displayArea = location || 'No location selected'

  useEffect(() => {
    const controller = new AbortController()
    setData(initialState)
    setLoading(true)
    const signal = controller.signal

    const load = (key, promise) => promise
      .then((result) => {
        if (!signal.aborted) setData((current) => ({ ...current, [key]: { data: result, error: '' } }))
      })
      .catch((cause) => {
        if (!signal.aborted && cause.name !== 'AbortError') {
          setData((current) => ({ ...current, [key]: { data: null, error: cause.message } }))
        }
      })

    const requests = [
      load('alerts', listAlerts({
        client_id: clientId,
        latitude: selectedLocation?.latitude,
        longitude: selectedLocation?.longitude,
        location_name: selectedLocation?.name,
        limit: 3,
      }, { signal })),
      load('reports', listVerifiedReports({ limit: 3, signal })),
      load('resources', listResources({
        search: selectedLocation?.name || '',
        limit: 3,
        offset: 0,
      }, { signal })),
    ]
    if (selectedLocation) requests.push(load('risk', assessFloodRisk(selectedLocation, { signal })))
    Promise.all(requests).finally(() => {
      if (!signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [clientId, selectedLocation])

  const risk = data.risk.data
  const riskStatus = risk?.assessment_status === 'available' ? risk.risk_level : 'Unknown'
  const riskTone = riskStatus === 'High' || riskStatus === 'Very High'
    ? 'red'
    : riskStatus === 'Moderate' ? 'amber' : 'teal'
  const alerts = data.alerts.data
  const reports = data.reports.data
  const resources = data.resources.data

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="MONITORING OVERVIEW"
        title="Situation overview"
        description={selectedLocation
          ? `Live weather and backend records for ${selectedLocation.name}${selectedLocation.admin1 ? `, ${selectedLocation.admin1}` : ''}. Resource matches are directory text matches, not a proximity search.`
          : 'Select a location to request weather and location-specific advisories. Other records below come from the backend.'}
        action={<span className="updated-chip"><span className="status-led" /> LIVE WEATHER · BACKEND RECORDS</span>}
      />

      <section className="metric-grid overview-live-metrics" aria-label="Current backend indicators">
        <article className="metric-card metric-risk">
          <div className="metric-top"><span className="metric-icon icon-amber"><ShieldAlert size={19} /></span><Pill tone={riskTone}>WEATHER-BASED</Pill></div>
          <div className="metric-label">Preliminary flood-risk indicator</div>
          <div className="metric-value">{selectedLocation ? metricValue(riskStatus, loading && !risk, data.risk.error) : 'Unknown'}</div>
          <div className="metric-foot"><span>{data.risk.error || (risk ? 'Not an official warning' : 'Select a location to assess')}</span></div>
        </article>
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon icon-red"><Radio size={19} /></span><Pill tone="red">BACKEND</Pill></div>
          <div className="metric-label">Active alert records</div>
          <div className="metric-value">{metricValue(alerts?.count, loading && !alerts, data.alerts.error)}</div>
          <div className="metric-foot"><span>{data.alerts.error || `${alerts?.unread_count ?? 0} unread for this browser`}</span></div>
        </article>
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon icon-teal"><MapPin size={19} /></span><Pill tone="teal">VERIFIED</Pill></div>
          <div className="metric-label">Verified flood reports</div>
          <div className="metric-value">{metricValue(reports?.count, loading && !reports, data.reports.error)}</div>
          <div className="metric-foot"><span>{data.reports.error || 'Count includes verified report records only'}</span></div>
        </article>
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon icon-cyan"><Droplets size={19} /></span><Pill tone="cyan">DIRECTORY</Pill></div>
          <div className="metric-label">{selectedLocation ? 'Directory matches for selected place' : 'Emergency resource records'}</div>
          <div className="metric-value">{metricValue(resources?.count, loading && !resources, data.resources.error)}</div>
          <div className="metric-foot"><span>{data.resources.error || 'Manually managed · availability not confirmed'}</span></div>
        </article>
      </section>

      <section className="overview-grid">
        <WeatherPanel location={selectedLocation} />
        <Panel className="alerts-panel" title="Active alerts" subtitle={selectedLocation ? `Current records · weather advisory checked for ${selectedLocation.name}` : 'Current active backend records'} action={<Link className="inline-link" to="/alerts">All alerts <ArrowRight size={14} /></Link>}>
          {data.alerts.error && <EmptyEmergencyState error title="Alerts unavailable" description={data.alerts.error} />}
          {!data.alerts.error && loading && !alerts && <EmptyEmergencyState loading title="Loading alerts" description="Checking current backend records…" />}
          {!data.alerts.error && !loading && alerts?.results.length === 0 && <EmptyEmergencyState title="No active alerts available" description="No alert has been generated to fill an empty result. Check official government channels." />}
          {!data.alerts.error && alerts?.results.length > 0 && <div className="emergency-alert-list">{alerts.results.map((alert) => <AlertCard key={alert.alert_id} alert={alert} compact />)}</div>}
          <p className="safety-note"><ShieldAlert size={15} /> Weather advisories are not official warnings. Follow local authority guidance.</p>
        </Panel>
      </section>

      <section className="overview-grid overview-grid-lower">
        <Panel title="Latest verified flood reports" subtitle="Community reports marked verified in FLOODGUARD; not government alerts" action={<Link className="inline-link" to="/reports">All reports <ArrowRight size={14} /></Link>}>
          {data.reports.error && <EmptyEmergencyState error title="Flood reports unavailable" description={data.reports.error} />}
          {!data.reports.error && loading && !reports && <EmptyEmergencyState loading title="Loading verified reports" description="Fetching report records…" />}
          {!data.reports.error && !loading && reports?.results.length === 0 && <EmptyEmergencyState title="No verified flood reports available" description="Pending or unverified submissions are not included here." />}
          {!data.reports.error && reports?.results.length > 0 && (
            <div className="overview-report-list">
              {reports.results.map((report) => (
                <article key={report.report_id} className="overview-report-row">
                  <span className="overview-report-icon"><CloudRain size={15} /></span>
                  <div><strong>{report.location_name}</strong><span>{report.severity} · {new Date(report.created_at).toLocaleString()}</span></div>
                  <Pill tone={report.severity === 'critical' ? 'red' : report.severity === 'high' ? 'amber' : 'neutral'}>VERIFIED</Pill>
                </article>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={selectedLocation ? 'Resources matching selected place' : 'Emergency resource directory'} subtitle={selectedLocation ? 'Name/address/district text search · not nearest facilities' : 'Directory records; operating status is not checked'} action={<Link className="inline-link" to="/resources">Open directory <ArrowRight size={14} /></Link>}>
          {data.resources.error && <EmptyEmergencyState error title="Resource directory unavailable" description={data.resources.error} />}
          {!data.resources.error && loading && !resources && <EmptyEmergencyState loading title="Loading directory records" description="Checking the emergency resource directory…" />}
          {!data.resources.error && !loading && resources?.results.length === 0 && <EmptyEmergencyState title="No matching resource records" description="No facilities are invented to fill this result. Browse official source links in the directory." />}
          {!data.resources.error && resources?.results.length > 0 && (
            <div className="resource-record-list overview-resource-list">
              {resources.results.map((resource) => <ResourceCard key={resource.resource_id} resource={resource} />)}
            </div>
          )}
        </Panel>
      </section>

      <div className="overview-bottom-links">
        <span><ShieldAlert size={14} /> Data may be incomplete or delayed; no service availability is guaranteed.</span>
        <Link to="/risk">Review weather-based risk details <ArrowRight size={14} /></Link>
      </div>
    </div>
  )
}
