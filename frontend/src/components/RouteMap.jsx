import { useEffect } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'

const riskColors = {
  Low: '#55d1b5',
  Moderate: '#edbd67',
  High: '#fb7474',
  'Very High': '#fb7474',
}

function FitRouteBounds({ route, alternatives, observations }) {
  const map = useMap()

  useEffect(() => {
    const coordinates = [
      ...route.geometry.coordinates,
      ...alternatives.flatMap((alternative) => alternative.geometry.coordinates),
      ...observations.map((observation) => [observation.longitude, observation.latitude]),
    ]
    const bounds = coordinates.map(([longitude, latitude]) => [latitude, longitude])
    if (bounds.length) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 })
  }, [alternatives, map, observations, route])

  return null
}

export default function RouteMap({ assessment }) {
  const alternatives = assessment.alternatives || []
  const observations = assessment.flood_observations?.observations || []
  const sachetAlerts = assessment.sachet_alerts?.alerts || []
  const weatherAssessments = assessment.weather_assessments || []
  const coordinates = assessment.route.geometry.coordinates.map(([longitude, latitude]) => [latitude, longitude])

  return (
    <div className="route-map" role="region" aria-label="Map showing the requested driving route and available risk information">
      <MapContainer center={coordinates[0]} zoom={11} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitRouteBounds route={assessment.route} alternatives={alternatives} observations={observations} />
        {alternatives.map((alternative, index) => (
          <Polyline
            key={`alternative-${index}`}
            positions={alternative.geometry.coordinates.map(([longitude, latitude]) => [latitude, longitude])}
            pathOptions={{ color: '#91a5ad', opacity: 0.65, dashArray: '5 7', weight: 4 }}
          />
        ))}
        <Polyline positions={coordinates} pathOptions={{ color: '#55d1d0', weight: 6, opacity: 0.92 }} />
        <CircleMarker center={coordinates[0]} radius={7} pathOptions={{ color: '#071724', weight: 2, fillColor: '#55d1b5', fillOpacity: 1 }}>
          <Tooltip>Starting point</Tooltip>
        </CircleMarker>
        <CircleMarker center={coordinates[coordinates.length - 1]} radius={7} pathOptions={{ color: '#071724', weight: 2, fillColor: '#e69c70', fillOpacity: 1 }}>
          <Tooltip>Destination</Tooltip>
        </CircleMarker>
        {observations.map((observation) => (
          <CircleMarker
            key={observation.report_id}
            center={[observation.latitude, observation.longitude]}
            radius={8}
            pathOptions={{
              color: observation.verification_status === 'verified' ? '#fb7474' : '#edbd67',
              weight: observation.verification_status === 'verified' ? 3 : 2,
              fillColor: observation.verification_status === 'verified' ? '#fb7474' : '#edbd67',
              fillOpacity: observation.verification_status === 'verified' ? 0.95 : 0.65,
              dashArray: observation.verification_status === 'pending' ? '3 3' : undefined,
            }}
          ><Tooltip>
            <strong>Citizen-submitted flood report</strong><br />
            {observation.location_name && <>{observation.location_name}<br /></>}
            Status: {observation.verification_status}<br />
            Severity: {observation.severity || 'Not provided'}<br />
            {observation.description || 'No description provided'}<br />
            {observation.created_at ? `Reported: ${new Date(observation.created_at).toLocaleString()}` : 'Report time unavailable'}
          </Tooltip></CircleMarker>
        ))}
        {sachetAlerts.map((alert) => (
          <CircleMarker
            key={alert.alert_id}
            center={[alert.latitude, alert.longitude]}
            radius={9}
            pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#66a9ff', fillOpacity: 0.95 }}
          ><Tooltip>
            <strong>Official SACHET alert</strong><br />
            {alert.headline || 'Headline unavailable'}<br />
            Source: {alert.source_name || 'NDMA SACHET'}<br />
            Published: {alert.source_published_at ? new Date(alert.source_published_at).toLocaleString() : 'Not provided'}
          </Tooltip></CircleMarker>
        ))}
        {weatherAssessments.map((weather, index) => weather.risk_level && (
          <CircleMarker
            key={`weather-${index}`}
            center={[weather.latitude, weather.longitude]}
            radius={5}
            pathOptions={{
              color: '#071724',
              weight: 1,
              fillColor: riskColors[weather.risk_level] || '#9aaab0',
              fillOpacity: 0.95,
            }}
          ><Tooltip>{weather.risk_level} weather-based indicator</Tooltip></CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
