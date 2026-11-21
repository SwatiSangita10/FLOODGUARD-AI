import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { AlertCard, EmptyEmergencyState } from '../components/EmergencyCards'
import { PageHeader, Panel } from '../components/UI'
import { getAlert, getAlertClientId, markAlertRead } from '../services/emergencyApi'

export default function AlertDetailPage() {
  const { alertId } = useParams()
  const [clientId] = useState(getAlertClientId)
  const [alert, setAlert] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [readError, setReadError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getAlert(alertId, clientId, { signal: controller.signal })
      .then(setAlert)
      .catch((cause) => {
        if (cause.name !== 'AbortError') setError(cause.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [alertId, clientId])

  async function handleMarkRead(id) {
    setReadError('')
    try {
      await markAlertRead(id, clientId)
      setAlert((current) => ({ ...current, is_read: true }))
    } catch (cause) {
      setReadError(cause.message)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="ALERT DETAILS"
        title={alert?.title || 'Alert details'}
        description="Source and current status are shown as returned by the FLOODGUARD backend."
        action={<Link className="secondary-button" to="/alerts"><ArrowLeft size={14} /> All alerts</Link>}
      />
      {loading && <EmptyEmergencyState loading title="Loading alert" description="Fetching the alert record…" />}
      {error && <EmptyEmergencyState error title="Alert unavailable" description={error} />}
      {!loading && !error && !alert && <EmptyEmergencyState title="Alert not found" description="This record may have expired or may no longer be available." />}
      {readError && <p className="emergency-inline-error" role="alert">Read status was not saved: {readError}</p>}
      {!loading && !error && alert && (
        <>
          <Panel title="Alert record" subtitle={alert.status === 'active' ? 'Active record' : `Record status: ${alert.status}`}>
            <AlertCard alert={alert} onMarkRead={!alert.is_read ? handleMarkRead : undefined} />
          </Panel>
          <Panel title="Safety information">
            <div className="notice-strip">
              <ShieldAlert size={17} />
              <div>
                <strong>Do not rely on this record as the only source of emergency information</strong>
                <span>Conditions and road access can change rapidly. Follow official evacuation instructions, contact local authorities directly, and never enter floodwater.</span>
              </div>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
