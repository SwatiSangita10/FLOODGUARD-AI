import { createElement as h } from 'react'
import {
  Ambulance, Building2, Clock3, ExternalLink, Flame, Hospital, MapPin, Phone,
  ShieldAlert, Siren, Waves,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const resourceIcons = {
  hospital: Hospital,
  fire_station: Flame,
  police_station: ShieldAlert,
  multipurpose_flood_shelter: Waves,
  multipurpose_cyclone_shelter: Waves,
  relief_centre: Building2,
  shelter: Building2,
  fire_rescue: Flame,
  police: ShieldAlert,
  disaster_management: Waves,
  ambulance: Ambulance,
  emergency_helpline: Siren,
}

const resourceLabels = {
  hospital: 'Hospital or medical facility',
  fire_station: 'Fire station',
  police_station: 'Police station',
  multipurpose_flood_shelter: 'Multipurpose flood shelter',
  multipurpose_cyclone_shelter: 'Multipurpose cyclone shelter',
  relief_centre: 'Relief centre',
  shelter: 'Emergency shelter or relief centre',
  fire_rescue: 'Fire and rescue service',
  police: 'Police station',
  disaster_management: 'Disaster management office',
  ambulance: 'Ambulance service',
  emergency_helpline: 'Emergency helpline',
}

const alertTones = {
  Information: 'teal',
  Advisory: 'amber',
  Warning: 'red',
  Emergency: 'red',
}

const alertSourceLabels = {
  official: 'Official government alert',
  sachet: 'Official SACHET feed entry',
  manual: 'Staff-managed notice',
  weather: 'Weather-based advisory · not official',
  community: 'Verified community report · not official',
}

function isCallable(number, verified) {
  if (!verified || !number) return false
  const digits = number.replace(/\D/g, '')
  return /^\+?[0-9][0-9\s().-]{5,24}$/.test(number) && digits.length >= 7 && digits.length <= 15
}

function formatTime(value) {
  if (!value) return 'Not provided'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : date.toLocaleString()
}

export function ResourceCard({ resource }) {
  const Icon = resourceIcons[resource.category] || Building2
  const verified = resource.verification_status === 'verified'
  const hasCoordinates = verified && Number.isFinite(resource.latitude) && Number.isFinite(resource.longitude)
  const directionsUrl = hasCoordinates
    ? `https://www.openstreetmap.org/?mlat=${resource.latitude}&mlon=${resource.longitude}#map=16/${resource.latitude}/${resource.longitude}`
    : null
  const phoneLink = isCallable(resource.contact_number, verified)
    ? `tel:${resource.contact_number.replace(/[^\d+]/g, '')}`
    : null

  return h('article', { className: 'resource-record-card' },
    h('div', { className: 'resource-record-icon' }, h(Icon, { size: 19 })),
    h('div', { className: 'resource-record-main' },
      h('div', { className: 'resource-record-heading' },
        h('h3', null, resource.name),
        h('span', { className: `resource-verification resource-verification-${verified ? 'verified' : 'unverified'}` },
          verified ? 'Verified' : 'Unverified',
        ),
      ),
      h('p', { className: 'resource-record-category' }, resourceLabels[resource.category] || resource.category),
      [
        resource.address,
        resource.village,
        resource.gram_panchayat,
        resource.block,
        resource.district,
        resource.state,
      ].some(Boolean) && h('p', { className: 'resource-record-location' },
        h(MapPin, { size: 13 }),
        [
          resource.address,
          resource.village,
          resource.gram_panchayat,
          resource.block,
          resource.district,
          resource.state,
        ].filter(Boolean).join(' · '),
      ),
      Number.isFinite(resource.capacity) && h('p', { className: 'resource-record-capacity' },
        `Published capacity: ${resource.capacity}`,
      ),
      verified && resource.operating_hours && h('p', { className: 'resource-record-hours' },
        h(Clock3, { size: 13 }),
        `Published hours: ${resource.operating_hours} · not a live open-status check`,
      ),
      h('div', { className: 'resource-record-source' },
        h('a', { href: resource.source_url, target: '_blank', rel: 'noreferrer' },
          `Source: ${resource.source_name}`, h(ExternalLink, { size: 12 }),
        ),
        h('span', null,
          verified
            ? `Last verified ${formatTime(resource.last_verified_at)}`
            : resource.last_verified_at
              ? `Previously verified ${formatTime(resource.last_verified_at)} · currently unverified`
              : 'Source has not been verified by the directory team',
        ),
        resource.last_updated_at && h('span', null,
          `Last updated ${formatTime(resource.last_updated_at)}`,
        ),
      ),
    ),
    h('div', { className: 'resource-record-actions' },
      phoneLink
        ? h('a', { className: 'secondary-button resource-action', href: phoneLink },
          h(Phone, { size: 14 }), 'Call',
        )
        : resource.contact_number
          ? h('span', { className: 'resource-contact-unverified' }, 'Unverified number · do not rely on it')
          : null,
      directionsUrl && h('a', {
        className: 'secondary-button resource-action',
        href: directionsUrl,
        target: '_blank',
        rel: 'noreferrer',
      }, h(MapPin, { size: 14 }), 'Directions'),
    ),
  )
}

export function AlertCard({ alert, onMarkRead, compact = false }) {
  const severityClass = alert.severity?.toLowerCase() || 'unknown'
  return h('article', {
    className: `emergency-alert-card${alert.is_read ? ' emergency-alert-read' : ''}${compact ? ' emergency-alert-compact' : ''}`,
  },
  h('span', { className: `emergency-alert-stripe emergency-alert-stripe-${severityClass}` }),
  h('div', { className: 'emergency-alert-body' },
    h('div', { className: 'emergency-alert-top' },
      alert.severity
        ? h('span', { className: `pill pill-${alertTones[alert.severity] || 'neutral'}` }, alert.severity)
        : null,
      alert.source_type === 'sachet' && !alert.source_published_at
        ? h('span', null, 'Publication time not provided in RSS')
        : h('time', { dateTime: alert.source_published_at || alert.created_at },
          `${alert.source_published_at ? 'Published' : 'Recorded'} · ${formatTime(alert.source_published_at || alert.created_at)}`,
        ),
      h('span', { className: `alert-read-status ${alert.is_read ? 'alert-read' : 'alert-unread'}` },
        alert.is_read ? 'Read' : 'Unread',
      ),
    ),
    h('h3', null, alert.title || (alert.source_type === 'sachet' ? 'Headline not provided in RSS' : 'Alert')),
    h('p', { className: 'emergency-alert-description' },
      alert.description || (
        alert.source_type === 'sachet'
          ? 'Description not provided in the RSS feed.'
          : ''
      ),
    ),
    h('div', { className: 'emergency-alert-meta' },
      h('span', null, alert.affected_location || (
        alert.source_type === 'sachet' ? 'Affected area not provided in RSS' : ''
      )),
      h('span', { className: `alert-source alert-source-${alert.source_type}` },
        alertSourceLabels[alert.source_type] || alert.source_name,
      ),
      alert.source_type === 'sachet' && alert.source_data?.rss_category
        ? h('span', null, `Feed category: ${alert.source_data.rss_category}`)
        : null,
      alert.event_type ? h('span', null, `Event: ${alert.event_type}`) : null,
      alert.urgency ? h('span', null, `Urgency: ${alert.urgency}`) : null,
      alert.effective_at
        ? h('span', null, `Effective · ${formatTime(alert.effective_at)}`)
        : null,
      alert.expires_at
        ? h('span', null, `Expires · ${formatTime(alert.expires_at)}`)
        : null,
      alert.source_verification_status === 'verified'
        ? h('span', { className: 'alert-source-verified' },
          alert.last_verified_at
            ? `Source verified · ${formatTime(alert.last_verified_at)}`
            : 'Report marked verified in FLOODGUARD',
        )
        : null,
      alert.source_url
        ? h('a', { href: alert.source_url, target: '_blank', rel: 'noreferrer' }, 'Source', h(ExternalLink, { size: 12 }))
        : alert.source_record_id
          ? h('a', { href: '/reports' }, 'Report record', h(ExternalLink, { size: 12 }))
          : null,
    ),
    alert.status === 'feed_entry'
          ? h('p', { className: 'emergency-source-status' },
            'The RSS entry does not confirm whether the alert is still valid. Verify it at the official source.',
          )
          : h(Link, { className: 'inline-link emergency-alert-details', to: `/alerts/${encodeURIComponent(alert.alert_id)}` },
            'View alert details', h(ExternalLink, { size: 12 }),
          ),
    !alert.is_read && onMarkRead && h('button', {
      className: 'text-button alert-mark-read',
      type: 'button',
      onClick: () => onMarkRead(alert.alert_id),
    }, 'Mark as read'),
  ),
  )
}

export function SachetFeedStatus({ feed, loading = false, error = '' }) {
  if (loading) {
    return h(EmptyEmergencyState, {
      loading: true,
      title: 'Checking official SACHET feed',
      description: 'The FLOODGUARD backend is checking the NDMA RSS feed.',
    })
  }
  if (error) {
    return h(EmptyEmergencyState, {
      error: true,
      title: 'SACHET feed status unavailable',
      description: 'The feed and its cached entries could not be loaded. Current official alert status is unknown.',
    })
  }
  if (!feed || feed.status === 'unavailable') {
    return h(EmptyEmergencyState, {
      error: true,
      title: 'SACHET feed could not be checked',
      description: 'Current official alert status is unknown. Check the NDMA SACHET portal directly.',
    })
  }

  const lastUpdate = feed.last_successful_update_at
    ? `Last successful feed update: ${formatTime(feed.last_successful_update_at)}.`
    : 'No successful feed update has been recorded.'
  const lastCheck = feed.last_successful_check_at
    ? ` Last successful check: ${formatTime(feed.last_successful_check_at)}.`
    : ''
  const hasRetainedEntries = feed.status === 'stale' && feed.count > 0
  const description = feed.status === 'stale'
    ? `${hasRetainedEntries
      ? 'The feed refresh failed; previously retrieved entries are retained and labelled for verification.'
      : 'The feed refresh failed and no cached entries are available; current official alert status is unknown.'} ${lastUpdate}${lastCheck}`
    : feed.status === 'empty'
      ? `The feed was checked and returned no unexpired entries. This does not establish that no hazard exists. ${lastUpdate}${lastCheck}`
      : `The official RSS feed is available. RSS entries do not necessarily include validity or expiry details; verify each original alert. ${lastUpdate}${lastCheck}`

  return h('div', {
    className: 'notice-strip sachet-feed-status',
    role: feed.status === 'stale' ? 'alert' : 'status',
  },
  h(ShieldAlert, { size: 17 }),
  h('div', null,
    h('strong', null, hasRetainedEntries ? 'Showing retained SACHET feed entries' : 'NDMA SACHET RSS feed'),
    h('span', null, description),
    h('a', {
      href: feed.source_url || 'https://sachet.ndma.gov.in/CapFeed',
      target: '_blank',
      rel: 'noreferrer',
    }, 'Open official SACHET portal', h(ExternalLink, { size: 12 })),
  ),
  )
}

export function EmptyEmergencyState({ title, description, loading = false, error = false }) {
  return h('div', {
    className: `empty-state${error ? ' emergency-empty-error' : ''}`,
    role: loading ? 'status' : error ? 'alert' : undefined,
  },
  loading ? h(Clock3, { size: 21 }) : h(ShieldAlert, { size: 21 }),
  h('strong', null, title),
  h('span', null, description),
  )
}

export { resourceLabels }
