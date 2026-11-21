import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, HeartPulse, Search, ShieldCheck } from 'lucide-react'
import { EmptyEmergencyState, ResourceCard, resourceLabels } from '../components/EmergencyCards'
import { PageHeader, Panel } from '../components/UI'
import { officialEmergencySources } from '../data/officialEmergencySources'
import { listResourceCategories, listResources } from '../services/emergencyApi'

const categoryOptions = Object.entries(resourceLabels)
  .filter(([value]) => value !== 'emergency_helpline')

export default function ResourcesPage() {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [district, setDistrict] = useState('')
  const [verificationStatus, setVerificationStatus] = useState('')
  const [page, setPage] = useState(null)
  const [facets, setFacets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [facetError, setFacetError] = useState('')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setOffset(0)
      setSearch(query.trim())
    }, 250)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    listResourceCategories({ signal: controller.signal })
      .then(setFacets)
      .catch((cause) => {
        if (cause.name !== 'AbortError') setFacetError(cause.message)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setPage(null)
    listResources({
      category,
      district,
      search,
      verification_status: verificationStatus,
      limit: 20,
      offset,
    }, { signal: controller.signal })
      .then(setPage)
      .catch((cause) => {
        if (cause.name !== 'AbortError') setError(cause.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [category, district, search, verificationStatus, offset])

  const displayedRange = useMemo(() => {
    if (loading) return 'Loading records…'
    if (error) return 'Unavailable'
    if (!page) return '—'
    if (!page.count) return '0 records'
    return `${offset + 1}–${offset + page.results.length} of ${page.count}`
  }, [error, loading, offset, page])

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="EMERGENCY SUPPORT"
        title="Emergency resources"
        description="A manually maintained directory. Verify availability directly with the responsible authority before travel."
        action={<span className="updated-chip"><ShieldCheck size={14} /> MANUALLY MANAGED DIRECTORY</span>}
      />

      <div className="resource-summary-grid">
        <div className="resource-summary-card">
          <span className="resource-summary-icon"><HeartPulse size={19} /></span>
          <div><strong>{facets ? facets.total_count : '—'}</strong><span>directory records</span></div>
        </div>
        <div className="resource-summary-card">
          <span className="resource-summary-icon"><ShieldCheck size={19} /></span>
          <div><strong>{facets ? facets.verified_count : '—'}</strong><span>marked verified</span></div>
        </div>
      </div>

      {facetError && <p className="emergency-inline-error" role="alert">Directory summary could not be loaded: {facetError}</p>}
      {facets && facets.verified_count === 0 && (
        <div className="notice-strip" role="status">
          <ShieldCheck size={17} />
          <div>
            <strong>No verified facilities are currently available</strong>
            <span>Unverified source entries, if shown below, have not been approved by the directory team.</span>
          </div>
        </div>
      )}

      <Panel className="resource-directory" title="Resource directory" subtitle={`${displayedRange} · records are not a live availability check`}>
        <div className="emergency-filter-grid">
          <label className="search-field">
            <Search size={16} /><span className="sr-only">Search resources by name or location</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name or location" />
          </label>
          <label className="sr-only" htmlFor="resource-category">Filter by category</label>
          <select id="resource-category" className="emergency-filter-select" value={category} onChange={(event) => { setCategory(event.target.value); setOffset(0) }}>
            <option value="">All categories</option>
            {categoryOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <label className="sr-only" htmlFor="resource-district">Filter by district</label>
          <select id="resource-district" className="emergency-filter-select" value={district} onChange={(event) => { setDistrict(event.target.value); setOffset(0) }}>
            <option value="">All districts</option>
            {facets?.districts.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <label className="sr-only" htmlFor="resource-verification">Filter by verification status</label>
          <select id="resource-verification" className="emergency-filter-select" value={verificationStatus} onChange={(event) => { setVerificationStatus(event.target.value); setOffset(0) }}>
            <option value="">All verification statuses</option>
            <option value="verified">Verified</option>
            <option value="unverified">Unverified</option>
          </select>
        </div>

        {error && <EmptyEmergencyState error title="Resource directory unavailable" description={error} />}
        {!error && loading && <EmptyEmergencyState loading title="Loading resource directory" description="Fetching records from the FLOODGUARD backend…" />}
        {!error && !loading && page?.results.length === 0 && (
          <EmptyEmergencyState
            title={search || category || district || verificationStatus ? 'No matching resources' : 'No resource records available'}
            description={search || category || district || verificationStatus
              ? 'Try changing or clearing the filters.'
              : facets?.verified_count === 0
                ? 'No facility records are available yet. Check the cited official sources below; no facilities are invented.'
                : 'No manually managed facility records are available. Use official source links below; no facilities are invented.'}
          />
        )}
        {!error && page?.results.length > 0 && (
          <div className="resource-record-list" aria-live="polite">
            {page.results.map((resource) => <ResourceCard key={resource.resource_id} resource={resource} />)}
          </div>
        )}
        {!error && page && page.count > 20 && (
          <div className="emergency-pagination">
            <button type="button" className="secondary-button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button>
            <span>{displayedRange}</span>
            <button type="button" className="secondary-button" disabled={page.next_offset === null || loading} onClick={() => setOffset(page.next_offset)}>Next</button>
          </div>
        )}
      </Panel>
      <div className="notice-strip" role="note">
        <ShieldCheck size={17} />
        <div>
          <span>Facility information is based on cited official sources. Availability, operating status and emergency access must be confirmed with the relevant authorities.</span>
        </div>
      </div>

      <Panel title="Official emergency references" subtitle="Open the source directly and confirm current contact details. FLOODGUARD does not claim that linked services are available or have been contacted.">
        <div className="official-source-grid">
          {officialEmergencySources.map((source) => (
            <article key={source.id} className="official-source-card">
              <div><span className="official-source-category">{source.category}</span><h3>{source.title}</h3></div>
              {source.address && <p>{source.address}</p>}
              {source.phoneNumbers?.map((number) => (
                <p className="official-source-phone" key={number}>
                  <strong>{number}</strong>
                  <a href={`tel:${number.replace(/\D/g, '')}`} aria-label={`Call listed OSDMA office number ${number}`}>Call</a>
                </p>
              ))}
              <p className="official-source-status">Source: {source.source} · Verification status: {source.status}</p>
              {source.checkedAt && <small>Source checked {source.checkedAt}; this does not verify current phone availability.</small>}
              <a className="inline-link" href={source.url} target="_blank" rel="noreferrer">Open official source <ExternalLink size={13} /></a>
            </article>
          ))}
        </div>
      </Panel>
      <div className="notice-strip" role="note">
        <HeartPulse size={17} />
        <div>
          <strong>Emergency information is not a dispatch service</strong>
          <span>No ambulance, rescue team, hospital, or shelter has been contacted. Published hours and listed contacts may be out of date; confirm with official authorities.</span>
        </div>
      </div>
    </div>
  )
}
