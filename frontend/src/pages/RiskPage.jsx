import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  AlertCircle, CheckCircle2, CloudRain, Database, RefreshCw, ShieldAlert,
} from 'lucide-react'
import { DemoNotice, PageHeader, Panel, Pill } from '../components/UI'
import { assessFloodRisk } from '../services/weatherApi'

function formatTime(value) {
  if (!value) return 'Unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'UTC',
    }).format(date) + ' UTC'
}

function RiskMessage({ icon: Icon, title, children, error = false }) {
  return (
    <div className={`risk-message${error ? ' risk-message-error' : ''}`} role={error ? 'alert' : 'status'}>
      <Icon size={20} aria-hidden="true" />
      <strong>{title}</strong>
      <span>{children}</span>
    </div>
  )
}

export default function RiskPage() {
  const { selectedLocation } = useOutletContext()
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(Boolean(selectedLocation))
  const [error, setError] = useState('')

  useEffect(() => {
    if (!selectedLocation) {
      setAssessment(null)
      setLoading(false)
      setError('')
      return undefined
    }

    const controller = new AbortController()
    setAssessment(null)
    setError('')
    setLoading(true)
    assessFloodRisk(selectedLocation, { signal: controller.signal })
      .then((response) => {
        if (!controller.signal.aborted) setAssessment(response)
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) setError(requestError.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [selectedLocation])

  async function reassess() {
    if (!selectedLocation || loading) return
    const controller = new AbortController()
    setLoading(true)
    setError('')
    try {
      setAssessment(await assessFloodRisk(selectedLocation, { signal: controller.signal }))
    } catch (requestError) {
      if (requestError.name !== 'AbortError') setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const score = assessment?.score
  const hasScore = Number.isFinite(score)
  const dataStatus = assessment?.weather_freshness?.status
  const badgeTone = assessment?.risk_level === 'Very High' || assessment?.risk_level === 'High'
    ? 'red'
    : assessment?.risk_level === 'Moderate' ? 'amber' : 'teal'

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="RISK MONITORING"
        title="AI flood risk"
        description="A preliminary, rules-based weather indicator for the selected location."
        action={<button className="secondary-button risk-refresh" onClick={reassess} disabled={!selectedLocation || loading}>
          <RefreshCw size={14} className={loading ? 'weather-spin' : ''} />
          {loading ? 'Assessing…' : 'Reassess'}
        </button>}
      />
      <DemoNotice>
        PRELIMINARY WEATHER-BASED INDICATOR · Not scientifically validated and not an official flood warning. Follow local authorities for emergency guidance.
      </DemoNotice>

      {!selectedLocation && <Panel title="Assessment unavailable" subtitle="Select a location to begin">
        <RiskMessage icon={CloudRain} title="No location selected">
          Choose a location from the top bar to request current weather and assess available precipitation data.
        </RiskMessage>
      </Panel>}

      {loading && <Panel title="Assessing weather conditions" subtitle={selectedLocation?.name || 'Selected location'}>
        <RiskMessage icon={RefreshCw} title="Loading live assessment">
          Retrieving current and forecast weather from Open-Meteo.
        </RiskMessage>
      </Panel>}

      {!loading && error && <Panel title="Assessment unavailable" subtitle={selectedLocation?.name}>
        <RiskMessage icon={AlertCircle} title="Could not load a live assessment" error>
          {error}
        </RiskMessage>
        <button className="secondary-button risk-retry" onClick={reassess}>Retry assessment</button>
      </Panel>}

      {!loading && !error && assessment && <>
        {dataStatus === 'stale' && <Panel title="Weather data is stale" subtitle={assessment.location.name}>
          <RiskMessage icon={AlertCircle} title="No risk level shown">
            The provider timestamp is outside the freshness window. Refresh later; stale weather is not scored.
          </RiskMessage>
        </Panel>}
        {assessment.assessment_status === 'unavailable' && dataStatus !== 'stale' && <Panel title="Weather data unavailable" subtitle={assessment.location.name}>
          <RiskMessage icon={AlertCircle} title="No risk level shown">
            The provider returned no usable precipitation measurements. Missing values are not estimated or replaced.
          </RiskMessage>
        </Panel>}

        <div className="risk-layout">
          <Panel className="risk-score-panel" title="Preliminary risk indicator" subtitle={assessment.location.name} action={hasScore && <Pill tone={badgeTone}>WEATHER-BASED</Pill>}>
            {hasScore ? <>
              <div className="risk-score-content">
                <div className={`risk-score-ring risk-score-${assessment.risk_level.toLowerCase().replace(' ', '-')}`} style={{ '--score-angle': `${score * 3.6}deg` }}>
                  <div><strong>{score}</strong><span>score / 100</span></div>
                </div>
                <div className="risk-score-copy">
                  <Pill tone={badgeTone}>{assessment.risk_level} · preliminary</Pill>
                  <h3>{assessment.location.name}</h3>
                  <p>{assessment.explanation}</p>
                </div>
              </div>
              <div className="score-scale"><span>Lower indicator</span><span>Higher indicator</span></div>
              <div className="score-track" aria-label={`Risk score ${score} out of 100`}><span style={{ width: `${score}%` }} /></div>
            </> : <RiskMessage icon={AlertCircle} title="Risk score not available">
              No score is calculated when weather data is stale or no usable rainfall measurements are provided.
            </RiskMessage>}
          </Panel>

          <Panel className="risk-factors-panel" title="Contributing weather factors" subtitle={assessment.data_completeness === 'complete' ? 'All four configured factors available' : 'Only available measurements are included'}>
            {assessment.factors.length
              ? <div className="risk-factor-list">{assessment.factors.map((factor) => <article className="risk-factor-card" key={factor.key}>
                <span className="risk-factor-icon"><CloudRain size={16} /></span>
                <div><strong>{factor.label}</strong><span>{factor.explanation}</span></div>
                <b>{factor.value} {factor.unit}</b>
              </article>)}</div>
              : <p className="risk-empty-factors">No precipitation factors could be assessed from the available weather response.</p>}
            {assessment.data_completeness === 'partial' && <div className="risk-partial-note">Some weather measurements were unavailable and excluded from scoring.</div>}
          </Panel>
        </div>

        <Panel className="risk-method-panel" title="Assessment details" subtitle="Transparent heuristic · no trained machine-learning model">
          <div className="risk-metadata-grid">
            <div><span>Assessed at</span><strong>{formatTime(assessment.assessed_at)}</strong></div>
            <div><span>Weather provider</span><strong>{assessment.provider?.name || 'Unavailable'}</strong></div>
            <div><span>Weather data timestamp</span><strong>{formatTime(assessment.weather_freshness?.provider_timestamp)}</strong></div>
            <div><span>Data status</span><strong className={`risk-data-status risk-data-${dataStatus}`}>{dataStatus || 'Unavailable'}{assessment.data_completeness === 'partial' ? ' · partial' : ''}</strong></div>
            <div><span>Location coordinates</span><strong>{assessment.location.latitude}, {assessment.location.longitude}</strong></div>
            <div><span>Snapshot persistence</span><strong>{assessment.snapshot?.status === 'stored' || assessment.snapshot?.status === 'recent_snapshot_exists' ? 'Saved to MongoDB' : 'Unavailable'}</strong></div>
          </div>
          <p className="risk-limitations"><ShieldAlert size={15} />{assessment.limitations}</p>
          <div className="risk-status-line"><CheckCircle2 size={15} /> This assessment uses Open-Meteo model data. It does not confirm flooding or replace an official warning.</div>
        </Panel>
      </>}
    </div>
  )
}
