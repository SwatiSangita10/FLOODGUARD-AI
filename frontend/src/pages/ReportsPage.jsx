import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Camera, FilePlus2, MapPin, RefreshCw, Search, ShieldAlert } from 'lucide-react'
import { PageHeader, Panel, Pill } from '../components/UI'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const PAGE_SIZE = 20
const severityOptions = ['low', 'moderate', 'high', 'critical']

function apiMessage(payload, fallback) {
  if (!payload) return fallback
  if (typeof payload.detail === 'string') return payload.detail
  if (typeof payload === 'string') return payload
  return Object.entries(payload).map(([field, messages]) => `${field}: ${Array.isArray(messages) ? messages.join(' ') : messages}`).join(' ')
}

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : date.toLocaleString()
}

export default function ReportsPage() {
  const [severity, setSeverity] = useState('')
  const [page, setPage] = useState({ results: [], count: 0, next_offset: null })
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [success, setSuccess] = useState('')

  const loadReports = useCallback(async (offset = 0, append = false) => {
    setLoading(true)
    setListError('')
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
      if (severity) params.set('severity', severity)
      const response = await fetch(`${API_BASE}/api/reports/?${params}`)
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(apiMessage(body, `Unable to load reports (${response.status}).`))
      setPage((current) => ({ ...body, results: append ? [...current.results, ...body.results] : body.results }))
    } catch (error) {
      setListError(error.message || 'Unable to connect to the report service.')
      if (!append) setPage({ results: [], count: 0, next_offset: null })
    } finally {
      setLoading(false)
    }
  }, [severity])

  useEffect(() => { loadReports() }, [loadReports])

  async function submitReport(event) {
    event.preventDefault()
    const form = event.currentTarget
    setSubmitting(true)
    setSubmitError('')
    setSuccess('')
    try {
      const response = await fetch(`${API_BASE}/api/reports/`, { method: 'POST', body: new FormData(form) })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(apiMessage(body, `Report submission failed (${response.status}).`))
      form.reset()
      setSuccess(`Report ${body.report_id} submitted for review.`)
      await loadReports()
    } catch (error) {
      setSubmitError(error.message || 'Unable to submit this report. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="COMMUNITY REPORTING" title="Flood reports" description="Submit an observed flood condition and review reports recorded by the service." />
      <div className="report-layout">
        <Panel className="report-table-panel" title="Citizen reports" subtitle="Reports are unverified until reviewed" action={<Pill tone="neutral">{page.count} REPORTS</Pill>}>
          <div className="report-toolbar">
            <label className="report-filter-label">Severity
              <select value={severity} onChange={(event) => setSeverity(event.target.value)} aria-label="Filter reports by severity">
                <option value="">All severities</option>{severityOptions.map((value) => <option value={value} key={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
              </select>
            </label>
            <button className="secondary-button report-refresh" onClick={() => loadReports()} disabled={loading}><RefreshCw size={14} /> Refresh</button>
          </div>
          {listError && <div className="report-feedback report-feedback-error" role="alert"><AlertCircle size={16} /><span>{listError}</span><button className="text-button" onClick={() => loadReports()}>Retry</button></div>}
          {loading && <div className="empty-state" role="status">Loading reports…</div>}
          {!loading && !listError && page.results.length === 0 && <div className="empty-state"><Search size={22} /><strong>No reports found</strong><span>Reports submitted to this service will appear here.</span></div>}
          {!loading && page.results.length > 0 && <div className="report-record-list">
            {page.results.map((report) => <article className="report-record" key={report.report_id}>
              <div className="report-record-main"><div className="report-record-heading"><span className={`severity-dot severity-${report.severity}`} /><strong>{report.location_name}</strong><Pill tone={report.status === 'pending' ? 'amber' : 'neutral'}>{report.status}</Pill></div>
                <div className="report-record-meta"><span><MapPin size={13} />{report.latitude.toFixed(5)}, {report.longitude.toFixed(5)}</span><time dateTime={report.created_at}>{formatDate(report.created_at)}</time></div>
                <p>{report.description}</p>
                {report.water_level != null && <small className="report-water-level">Reported water level: {report.water_level}</small>}
              </div>
              {report.photo_url && <a className="report-photo-link" href={report.photo_url} target="_blank" rel="noreferrer"><img src={report.photo_url} alt={`Citizen photo for report at ${report.location_name}`} loading="lazy" /></a>}
            </article>)}
          </div>}
          {!loading && page.next_offset != null && <button className="secondary-button report-load-more" onClick={() => loadReports(page.next_offset, true)}>Load more reports</button>}
          <div className="table-note"><ShieldAlert size={15} /> Reports are citizen submissions and may not be independently verified. Follow official emergency guidance.</div>
        </Panel>
        <Panel className="report-form-panel" title="Submit a flood report" subtitle="New submissions enter pending review">
          <form className="report-form" onSubmit={submitReport}>
            <label>Location name<input name="location_name" maxLength="160" placeholder="Street, landmark, or area" required /></label>
            <div className="report-coordinate-grid">
              <label>Latitude<input name="latitude" type="number" min="-90" max="90" step="any" placeholder="e.g. 12.9716" required /></label>
              <label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" placeholder="e.g. 77.5946" required /></label>
            </div>
            <label>Severity<select name="severity" defaultValue="moderate" required>{severityOptions.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
            <label>Water level <span className="field-optional">optional</span><input name="water_level" type="number" min="0" step="any" placeholder="Value and unit as observed" /></label>
            <label>Description<textarea name="description" maxLength="2000" rows="4" placeholder="Describe the observed conditions" required /></label>
            <label className="report-photo-input"><Camera size={17} /><span>Photo <small>optional · JPEG, PNG, WebP · up to 5 MB</small></span><input name="photo" type="file" accept="image/jpeg,image/png,image/webp" /></label>
            {submitError && <div className="report-feedback report-feedback-error" role="alert"><AlertCircle size={16} />{submitError}</div>}
            {success && <div className="report-feedback report-feedback-success" role="status">{success}</div>}
            <button className="primary-button" type="submit" disabled={submitting}><FilePlus2 size={16} />{submitting ? 'Submitting…' : 'Submit report'}</button>
            <p className="form-disclaimer">Submitted reports are stored by the backend with status pending. Do not use this form to request emergency dispatch.</p>
          </form>
        </Panel>
      </div>
    </div>
  )
}
