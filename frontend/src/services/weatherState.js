export function createWeatherState(locationSelected) {
  return {
    weather: null,
    status: locationSelected ? 'loading' : 'empty',
    error: '',
    storageWarning: '',
  }
}

export function weatherStateReducer(state, action) {
  switch (action.type) {
    case 'location_changed':
      return createWeatherState(action.locationSelected)
    case 'success':
      return {
        weather: action.weather,
        status: 'success',
        error: '',
        storageWarning: action.storageWarning || '',
      }
    case 'failure':
      return {
        weather: action.keepWeather ? state.weather : null,
        status: action.keepWeather && state.weather ? 'stale' : 'unavailable',
        error: action.message,
        storageWarning: action.keepWeather ? state.storageWarning : '',
      }
    default:
      return state
  }
}
