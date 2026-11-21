import { useEffect, useState } from 'react'
import { Bell, Contrast, Globe, Info, LockKeyhole, Monitor, Settings2 } from 'lucide-react'
import { DemoNotice, PageHeader, Panel, Pill } from '../components/UI'

export default function SettingsPage() {
  const [compact, setCompact] = useState(() => sessionStorage.getItem('fg-compact') === 'true')
  const [quietAlerts, setQuietAlerts] = useState(() => sessionStorage.getItem('fg-quiet-alerts') === 'true')

  useEffect(() => {
    document.documentElement.dataset.compactWorkspace = String(compact)
    sessionStorage.setItem('fg-compact', String(compact))
  }, [compact])

  useEffect(() => {
    document.documentElement.dataset.quietAlerts = String(quietAlerts)
    sessionStorage.setItem('fg-quiet-alerts', String(quietAlerts))
  }, [quietAlerts])

  return (
    <div className="page-stack settings-page">
      <PageHeader eyebrow="WORKSPACE PREFERENCES" title="Settings" description="Review local display preferences and service configuration." action={<Pill tone="demo">DEMO WORKSPACE</Pill>} />
      <DemoNotice>Preferences on this page only affect this browser session. No account or settings service is connected.</DemoNotice>
      <div className="settings-layout">
        <Panel className="settings-panel" title="Display preferences" subtitle="Local session controls">
          <div className="settings-option"><span className="settings-option-icon"><Monitor size={18} /></span><div className="settings-option-copy"><strong>Compact workspace</strong><span>Reduce spacing between dashboard panels in this session.</span></div><label className="toggle-control"><input type="checkbox" checked={compact} onChange={(event) => setCompact(event.target.checked)} /><span className="toggle-slider" /><span className="sr-only">Compact workspace</span></label></div>
          <div className="settings-option"><span className="settings-option-icon"><Bell size={18} /></span><div className="settings-option-copy"><strong>Hide unread alert count</strong><span>Hide the backend unread-count badge in this browser session.</span></div><label className="toggle-control"><input type="checkbox" checked={quietAlerts} onChange={(event) => setQuietAlerts(event.target.checked)} /><span className="toggle-slider" /><span className="sr-only">Hide unread alert count</span></label></div>
          <div className="settings-option"><span className="settings-option-icon"><Contrast size={18} /></span><div className="settings-option-copy"><strong>Appearance</strong><span>Dark navy theme · the only available theme in this build.</span></div><Pill tone="neutral">DARK</Pill></div>
          <div className="settings-option"><span className="settings-option-icon"><Globe size={18} /></span><div className="settings-option-copy"><strong>Language</strong><span>Interface language configuration is not connected.</span></div><Pill tone="neutral">EN</Pill></div>
          <p className="form-disclaimer">Display changes take effect immediately and remain in this browser session only.</p>
        </Panel>
        <Panel className="settings-status-panel" title="Integration status" subtitle="Upstream services are checked when a feature requests them">
          <div className="service-row"><span className="service-status-icon"><Monitor size={16} /></span><div><strong>Frontend</strong><small>React application</small></div><Pill tone="green">ACTIVE</Pill></div>
          <div className="service-row"><span className="service-status-icon"><Settings2 size={16} /></span><div><strong>Django REST API</strong><small>This status panel checks /api/health/ only; feature endpoints are requested separately.</small></div><Pill tone="amber">BASIC</Pill></div>
          <div className="service-row"><span className="service-status-icon"><Globe size={16} /></span><div><strong>Open-Meteo and OSRM</strong><small>Requested by weather, risk, and route features</small></div><Pill tone="neutral">ON DEMAND</Pill></div>
          <div className="service-row"><span className="service-status-icon"><LockKeyhole size={16} /></span><div><strong>MongoDB and Gemini</strong><small>MongoDB is checked by data operations. Gemini's last real request returned HTTP 503; current availability is unverified.</small></div><Pill tone="amber">GEMINI 503</Pill></div>
          <div className="settings-info"><Info size={16} /><span>Credentials are configured server-side and are not stored in this frontend. A configured integration is not a guarantee that its upstream service is available.</span></div>
        </Panel>
      </div>
    </div>
  )
}
