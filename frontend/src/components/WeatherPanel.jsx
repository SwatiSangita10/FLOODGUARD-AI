import { useEffect, useReducer, useRef, useState } from 'react'
import {
  AlertCircle, Cloud, CloudLightning, CloudRain, CloudSnow, CloudSun,
  RefreshCw, ShieldAlert, Sun,
} from 'lucide-react'
import { getWeatherCondition } from '../data/weatherConditions'
import { fetchWeather } from '../services/weatherApi'
import { createWeatherState, weatherStateReducer } from '../services/weatherState'
import { Panel, Pill } from './UI'

function display(value, unit = '') {
  return value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : `${value}${unit}`
}

function formatProviderTime(value) {
  if (!value) return 'Unavailable'
  return value.replace('T', ' ')
}

function formatFetchedTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unavailable' : `${new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(date)} UTC`
}

function formatAge(value) {
  const ageMinutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000))
  if (!Number.isFinite(ageMinutes)) return 'Update time unavailable'
  return ageMinutes < 1 ? 'Fetched just now' : `Fetched ${ageMinutes} min ago`
}

const conditionIcons = { sun: Sun, 'cloud-sun': CloudSun, cloud: Cloud, fog: Cloud, rain: CloudRain, snow: CloudSnow, storm: CloudLightning }

function WeatherStatus({ status, error, onRetry, storageWarning }) {
  if (status === 'loading') return <div className="weather-state" role="status"><RefreshCw className="weather-spin" size={20} /><strong>Loading live weather…</strong><span>Requesting current conditions and forecast from Open-Meteo.</span></div>
  if (status === 'empty') return <div className="weather-state"><CloudSun size={22} /><strong>No location selected</strong><span>Choose a geocoded location in the top bar to load real weather conditions.</span></div>
  if (status === 'unavailable') return <div className="weather-state weather-state-error" role="alert"><AlertCircle size={20} /><strong>Live weather unavailable</strong><span>{error}</span><button className="secondary-button" onClick={onRetry}>Retry</button></div>
  return <>
    {status === 'stale' && <div className="weather-feedback weather-feedback-stale" role="status"><AlertCircle size={15} />{error ? `Refresh failed. Showing the last successful live response, marked stale. ${error}` : 'This live response is older than ten minutes.'}</div>}
    {storageWarning && <div className="weather-feedback weather-feedback-stale" role="status"><AlertCircle size={15} />{storageWarning} The live response is shown but its snapshot was not saved.</div>}
  </>
}

export default function WeatherPanel({ location }) {
  const [weatherState, dispatch] = useReducer(weatherStateReducer, Boolean(location), createWeatherState)
  const { weather, status, error, storageWarning } = weatherState
  const [refreshing, setRefreshing] = useState(false)
  const [clockTick, setClockTick] = useState(Date.now())
  const refreshController = useRef(null)

  useEffect(() => {
    if (!location) {
      dispatch({ type: 'location_changed', locationSelected: false })
      return undefined
    }

    const controller = new AbortController()
    dispatch({ type: 'location_changed', locationSelected: true })
    fetchWeather(location, { signal: controller.signal })
      .then(({ weather: response, storageError: persistenceError }) => {
        if (controller.signal.aborted) return
        dispatch({ type: 'success', weather: response, storageWarning: persistenceError })
      })
      .catch((requestError) => {
        if (controller.signal.aborted) return
        dispatch({ type: 'failure', message: requestError.message, keepWeather: false })
      })
    return () => {
      controller.abort()
      refreshController.current?.abort()
    }
  }, [location])

  useEffect(() => {
    if (!weather) return undefined
    const timer = window.setInterval(() => setClockTick(Date.now()), 60_000)
    return () => window.clearInterval(timer)
  }, [weather])

  async function refresh() {
    if (!location || refreshing) return
    const controller = new AbortController()
    refreshController.current = controller
    setRefreshing(true)
    try {
      const response = await fetchWeather(location, { signal: controller.signal })
      dispatch({ type: 'success', weather: response.weather, storageWarning: response.storageError })
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        dispatch({ type: 'failure', message: requestError.message, keepWeather: true })
      }
    } finally {
      if (refreshController.current === controller) {
        refreshController.current = null
        setRefreshing(false)
      }
    }
  }

  const current = weather?.current
  const currentValues = current?.values || {}
  const currentUnits = current?.units || {}
  const code = currentValues.weather_code
  const condition = getWeatherCondition(code)
  const ConditionIcon = conditionIcons[condition.icon] || Cloud
  const hourlyTimes = weather?.hourly?.time || []
  const hourlyValues = weather?.hourly?.values || {}
  const hourlyUnits = weather?.hourly?.units || {}
  const hourlyRain = hourlyValues.precipitation || []
  const maxHourlyRain = Math.max(0, ...hourlyRain.map((value) => Number(value) || 0))
  const dailyTimes = weather?.daily?.time || []
  const dailyValues = weather?.daily?.values || {}
  const dailyUnits = weather?.daily?.units || {}
  const isOld = weather?.fetched_at && clockTick - new Date(weather.fetched_at).getTime() > 10 * 60 * 1000
  const displayStatus = status === 'success' && isOld ? 'stale' : status
  const providerLocalTime = formatProviderTime(current?.time)

  return (
    <Panel className="weather-panel" title="Live weather and rainfall" subtitle={location ? `${location.name}${location.admin1 ? `, ${location.admin1}` : ''} · current model conditions and forecasts` : 'Select a location to request weather data'} action={<div className="weather-panel-actions">{weather && <Pill tone={displayStatus === 'stale' ? 'amber' : 'teal'}>{displayStatus === 'stale' ? 'STALE DATA' : 'LIVE DATA'}</Pill>}<button className="icon-button weather-refresh" onClick={refresh} disabled={!location || refreshing} aria-label="Refresh weather"><RefreshCw size={15} className={refreshing ? 'weather-spin' : ''} /></button></div>}>
      <WeatherStatus status={displayStatus === 'stale' ? 'stale' : status} error={error} onRetry={refresh} storageWarning={storageWarning} />
      {weather && <div className="weather-live-content">
        <div className="weather-current-summary">
          <div className="weather-condition"><span className="weather-condition-icon"><ConditionIcon size={26} /></span><div><strong>{condition.description}</strong><span>Model-based current conditions · {weather.location.timezone}</span></div></div>
          <div className="weather-temperature"><strong>{display(currentValues.temperature_2m, currentUnits.temperature_2m)}</strong><span>Feels like {display(currentValues.apparent_temperature, currentUnits.apparent_temperature)}</span></div>
        </div>
        <div className="weather-measure-grid">
          <WeatherMetric label="Humidity" value={display(currentValues.relative_humidity_2m, currentUnits.relative_humidity_2m)} />
          <WeatherMetric label="Current precipitation" value={display(currentValues.precipitation, currentUnits.precipitation)} note="Model-based · not a station observation" />
          <WeatherMetric label="Rain" value={display(currentValues.rain, currentUnits.rain)} />
          <WeatherMetric label="Wind speed" value={display(currentValues.wind_speed_10m, currentUnits.wind_speed_10m)} />
          <WeatherMetric label="Sea-level pressure" value={display(currentValues.pressure_msl, currentUnits.pressure_msl)} />
          <WeatherMetric label="Cloud cover" value={display(currentValues.cloud_cover, currentUnits.cloud_cover)} />
        </div>

        <div className="weather-forecasts">
          <section className="weather-forecast-block">
            <div className="weather-subheading"><div><strong>Hourly precipitation</strong><span>Forecast · next 24 hours</span></div><small>{hourlyUnits.precipitation || 'mm'}</small></div>
            {hourlyTimes.length ? <>
              <div className="hourly-chart" role="list" aria-label="Hourly precipitation forecast">
                {hourlyTimes.map((time, index) => {
                  const amount = hourlyRain[index]
                  const probability = hourlyValues.precipitation_probability?.[index]
                  const numericAmount = Number(amount)
                  const height = maxHourlyRain && Number.isFinite(numericAmount) ? (numericAmount / maxHourlyRain) * 100 : 0
                  return <span role="listitem" className="hourly-bar-slot" key={`${time}-${index}`} title={`${time.replace('T', ' ')} ${weather.location.timezone}: ${display(amount, ` ${hourlyUnits.precipitation || 'mm'}`)} precipitation, ${display(probability, '%')} probability`}><i style={{ height: `${height}%` }} /></span>
                })}
              </div>
              <div className="hourly-axis"><span>{hourlyTimes[0]?.slice(11, 16)}</span><span>{hourlyTimes[6]?.slice(11, 16)}</span><span>{hourlyTimes[12]?.slice(11, 16)}</span><span>{hourlyTimes[18]?.slice(11, 16)}</span><span>{hourlyTimes.at(-1)?.slice(11, 16)}</span></div>
              <div className="hourly-details"><span>Hour</span><span>Precipitation ({hourlyUnits.precipitation || 'mm'})</span><span>Probability</span>{hourlyTimes.map((time, index) => <WeatherHour key={`${time}-detail`} time={time} zone={weather.location.timezone} amount={hourlyRain[index]} unit={hourlyUnits.precipitation} probability={hourlyValues.precipitation_probability?.[index]} />)}</div>
            </> : <p className="weather-muted">Hourly forecast unavailable from the provider.</p>}
          </section>
          <section className="weather-forecast-block">
            <div className="weather-subheading"><div><strong>Daily outlook</strong><span>Forecast · next 7 days</span></div><small>{dailyUnits.precipitation_sum || 'mm'}</small></div>
            <div className="daily-forecast-list">
              {dailyTimes.map((date, index) => {
                const dailyCondition = getWeatherCondition(dailyValues.weather_code?.[index])
                const DailyIcon = conditionIcons[dailyCondition.icon] || Cloud
                return <article className="daily-forecast-row" key={date}><time dateTime={date}>{new Date(`${date}T12:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: weather.location.timezone })}</time><span className="daily-condition"><DailyIcon size={15} />{dailyCondition.description}</span><span>{display(dailyValues.temperature_2m_min?.[index], dailyUnits.temperature_2m_min)} / {display(dailyValues.temperature_2m_max?.[index], dailyUnits.temperature_2m_max)}</span><strong>{display(dailyValues.precipitation_sum?.[index], ` ${dailyUnits.precipitation_sum || 'mm'}`)}</strong><small>{display(dailyValues.precipitation_probability_max?.[index], '%')}</small></article>
              })}
            </div>
            <div className="daily-forecast-legend"><span>Min / max temperature</span><span>Precipitation</span><span>Max probability</span></div>
          </section>
        </div>
        <div className="weather-data-footer">
          <div><span>Provider timestamp</span><strong>{providerLocalTime} {weather.location.timezone_abbreviation || weather.location.timezone}</strong></div>
          <div><span>Application fetched at</span><strong>{formatFetchedTime(weather.fetched_at)} · {formatAge(weather.fetched_at)}</strong></div>
          <div><a href={weather.source.attribution_url} target="_blank" rel="noreferrer">Weather data: Open-Meteo</a><span>Current conditions are model-based. Forecast precipitation is not observed rainfall.</span></div>
          <p><ShieldAlert size={14} /> Weather data alone does not confirm flooding. Follow official local guidance.</p>
        </div>
      </div>}
    </Panel>
  )
}

function WeatherMetric({ label, value, note }) {
  return <div className="weather-metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
}

function WeatherHour({ time, zone, amount, unit, probability }) {
  return <><time>{time.slice(11, 16)} <small>{zone}</small></time><span>{display(amount, ` ${unit || 'mm'}`)}</span><span>{display(probability, '%')}</span></>
}
